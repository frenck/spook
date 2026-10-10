"""Spook - Your homie. Telling a state an entity can be in from one it never is.

Only for entities whose states are a fixed set: what Home Assistant itself
says the kind of entity can be, or the options the entity offers. A plain
sensor can be anything, so nothing it is asked to be is ever impossible.

On top of that set comes everything the entity was: right now, every state
Spook saw it in, and every state the recorder remembers.

A set is only a promise where core keeps it. For some kinds of entity core
writes nothing outside of it, so anything else can never happen. For the
rest the set is what is usual, not what is possible: a media player made
from a template can be in any state it likes, and a select can get new
options at any moment. No amount of history proves either never will be
in a state. Those only get a state reported that differs from
a known one in case alone, and only when the whole history agrees.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from enum import StrEnum
import importlib
import inspect
import sys
from typing import TYPE_CHECKING, Final

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from homeassistant.components.recorder import is_entity_recorded
from homeassistant.components.recorder.db_schema import States
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import split_entity_id
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.recorder import get_instance, session_scope
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .attribute_checking import (
    NEWS_OVERLAP,
    HistoryAnswer,
    answers_to_continue,
    recorder_can_answer,
    recorder_metadata_ids,
    suggest_name,
)
from .const import LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime
    from types import ModuleType

    from sqlalchemy.orm import Session

    from homeassistant.core import HomeAssistant, State

# The domains whose states core lists in an enum of their own, and where it
# lives. Only where to find it: the states themselves are read from core, so
# a release adding one is picked up without Spook doing anything. Every one
# of these is in core from 2026.8 on. An enum that cannot be found means the
# domain is not checked at all, rather than checked against a guess.
_STATE_ENUMS: Final = {
    "alarm_control_panel": ("const", "AlarmControlPanelState"),
    "assist_satellite": ("entity", "AssistSatelliteState"),
    "camera": ("const", "CameraState"),
    "climate": ("const", "HVACMode"),
    "cover": ("const", "CoverState"),
    "lawn_mower": ("const", "LawnMowerActivity"),
    "lock": ("const", "LockState"),
    "media_player": ("const", "MediaPlayerState"),
    "vacuum": ("const", "VacuumActivity"),
    "valve": ("const", "ValveState"),
}

_ON_OFF = ("on", "off")

# The states of the domains core has no enum for, from the frontend's
# `FIXED_DOMAIN_STATES`, the list its state pickers offer. Left out: the
# domains above, whose enum is read instead, person and device tracker,
# whose states are zone names, and domains the frontend lists without any.
_FIXED_STATES: Final[dict[str, tuple[str, ...]]] = {
    "alert": ("on", "off", "idle"),
    "automation": _ON_OFF,
    "binary_sensor": _ON_OFF,
    "calendar": _ON_OFF,
    "fan": _ON_OFF,
    "humidifier": _ON_OFF,
    "input_boolean": _ON_OFF,
    "light": _ON_OFF,
    "plant": ("ok", "problem"),
    "remote": _ON_OFF,
    "schedule": _ON_OFF,
    "script": _ON_OFF,
    "siren": _ON_OFF,
    "sun": ("above_horizon", "below_horizon"),
    "switch": _ON_OFF,
    "timer": ("active", "idle", "paused"),
    "update": _ON_OFF,
    "weather": (
        "clear-night",
        "cloudy",
        "exceptional",
        "fog",
        "hail",
        "lightning-rainy",
        "lightning",
        "partlycloudy",
        "pouring",
        "rainy",
        "snowy-rainy",
        "snowy",
        "sunny",
        "windy-variant",
        "windy",
    ),
}

# The attribute listing what an entity of a domain can be: the options it
# offers, or for a climate entity the modes, which come on top of its enum.
# Water heaters are left out on purpose: their state is the current
# operation, which core does not hold to the list, and some integrations
# report `off` without offering it.
_OPTIONS_ATTRIBUTES: Final = {
    "climate": "hvac_modes",
    "input_select": "options",
    "select": "options",
    "sensor": "options",
}

# A sensor offers options only as an enum: any other sensor can be anything.
_ENUM_SENSOR = "enum"

_TOGGLE = ("homeassistant.helpers.entity", "ToggleEntity")

# Where core keeps the set: the class whose `state` writes nothing outside of
# it, read in core's source. Only sets that are the same for every entity of
# the domain: a select or an enum sensor is held to the options it has right
# now, and those change, by a template or a script setting new ones, so
# what is not an option today can be one tomorrow. An entity counts only while its `state` is that
# very one, so a subclass that brings its own does not. Python leaves no mark
# at runtime for a `final` written above `property`, which is how most of
# these are written, so being that very property is what is checked.
_KEPT_BY: Final = {
    # On, off or nothing, from `is_on`.
    "automation": _TOGGLE,
    "fan": _TOGGLE,
    "humidifier": _TOGGLE,
    "input_boolean": _TOGGLE,
    "light": _TOGGLE,
    "remote": _TOGGLE,
    "script": _TOGGLE,
    "siren": _TOGGLE,
    "switch": _TOGGLE,
    # On, off or nothing, from `is_on`.
    "binary_sensor": ("homeassistant.components.binary_sensor", "BinarySensorEntity"),
    # On or off, from whether an event is going on.
    "calendar": ("homeassistant.components.calendar", "CalendarEntity"),
    # On, off or nothing, from comparing versions.
    "update": ("homeassistant.components.update", "UpdateEntity"),
    # A member of its enum or nothing, worked out from the flags it has.
    "cover": ("homeassistant.components.cover", "CoverEntity"),
    "lock": ("homeassistant.components.lock", "LockEntity"),
    "valve": ("homeassistant.components.valve", "ValveEntity"),
    "camera": ("homeassistant.components.camera", "Camera"),
    # Whatever the mode is, made into its enum, which refuses anything else.
    "climate": ("homeassistant.components.climate", "ClimateEntity"),
}

# States any entity can be in, whatever its domain: Home Assistant's own for
# an entity that cannot say, or does not know.
_ALWAYS_VALID: Final = frozenset({STATE_UNAVAILABLE, STATE_UNKNOWN})

# How much of an entity's history is read, newest first, bounded in the
# database itself. An entity with more is read partially, and then nothing
# missing from it is reported, because the part not read might have had it.
MOST_STATES_PER_ENTITY: Final = 50_000

DATA_DOMAIN_STATES: HassKey[dict[str, frozenset[str] | None]] = HassKey(
    "spook_domain_states"
)
DATA_STATE_KNOWLEDGE: HassKey[dict[str, _Knowledge]] = HassKey("spook_state_knowledge")


@dataclass(frozen=True, slots=True)
class UnknownState:
    """A state somebody named that its entity is never in."""

    entity_id: str
    state: str
    suggestion: str | None


@dataclass(slots=True)
class _Knowledge:
    """What Spook knows about the states of one entity."""

    # Every state ever seen, on the entity or in the recorder. Grows only: a
    # state purged from history was still real.
    seen: set[str] = field(default_factory=set)
    # Every option the entity ever offered. Grows only too: options come and
    # go, like a source list, and one gone now may well come back.
    offered: set[str] = field(default_factory=set)
    answer: HistoryAnswer | None = None

    def see(self, state: str) -> None:
        """Note the state the entity is in right now.

        A state not seen before means the entity changed since the recorder
        was asked, so its answer no longer tells the whole story.
        """
        if state not in self.seen:
            self.seen.add(state)
            self.answer = None


def _states_from_module(module: ModuleType, enum_name: str) -> frozenset[str] | None:
    """Return the states an enum in a module lists, if it is there."""
    enum = getattr(module, enum_name, None)
    if not isinstance(enum, type) or not issubclass(enum, StrEnum):
        return None
    return frozenset(member.value for member in enum)


async def async_domain_states(
    hass: HomeAssistant, domain: str
) -> frozenset[str] | None:
    """Return the states entities of a domain can be in, or None if not fixed.

    Read live from core where it has an enum for them, imported off the
    event loop the first time, and remembered per domain from then on. A
    domain whose enum fails to import has no fixed states: that makes Spook
    say less, never more.
    """
    known = hass.data.setdefault(DATA_DOMAIN_STATES, {})
    if domain in known:
        return known[domain]

    if (where := _STATE_ENUMS.get(domain)) is None:
        fixed = _FIXED_STATES.get(domain)
        states = None if fixed is None else frozenset(fixed)
        known[domain] = states
        return states

    module_name = f"homeassistant.components.{domain}.{where[0]}"
    if (module := sys.modules.get(module_name)) is None:
        try:
            module = await hass.async_add_import_executor_job(
                importlib.import_module, module_name
            )
        # An integration's package can fail to import in any way it likes,
        # and none of them are a reason to fail an inspection.
        # pylint: disable-next=broad-exception-caught
        except Exception:  # noqa: BLE001
            LOGGER.debug("Spook found no state enum for %s", domain)
            module = None

    states = None if module is None else _states_from_module(module, where[1])
    known[domain] = states
    return states


def _offered(domain: str, state: State) -> set[str]:
    """Return the options the entity offers right now, if its domain has any."""
    if (attribute := _OPTIONS_ATTRIBUTES.get(domain)) is None:
        return set()
    if domain == "sensor" and state.attributes.get("device_class") != _ENUM_SENSOR:
        return set()

    options = state.attributes.get(attribute)
    if not isinstance(options, list | tuple):
        return set()
    return {option for option in options if isinstance(option, str)}


def _entity_object(hass: HomeAssistant, entity_id: str) -> object | None:
    """Return the entity its domain holds, if it is one and not just a state.

    Anything can set a state: a REST call, a Python script, a statestream.
    Those say nothing about what the domain can be, so only entities their
    domain loaded itself are checked.
    """
    component = hass.data.get(DATA_INSTANCES, {}).get(split_entity_id(entity_id)[0])
    return None if component is None else component.get_entity(entity_id)


def _set_is_kept(domain: str, entity: object) -> bool:
    """Return whether core writes nothing outside of the set for this entity.

    Only for a domain where core does, and only while the entity's `state`
    is core's own: a subclass with a `state` of its own can say anything.
    """
    if (where := _KEPT_BY.get(domain)) is None:
        return False

    keeper = getattr(sys.modules.get(where[0]), where[1], None)
    if not isinstance(keeper, type) or not isinstance(entity, keeper):
        return False

    kept = inspect.getattr_static(keeper, "state", None)
    return kept is not None and inspect.getattr_static(type(entity), "state") is kept


def _knowledge(hass: HomeAssistant, entity_id: str) -> _Knowledge:
    """Return what Spook knows about an entity, starting from nothing."""
    known = hass.data.setdefault(DATA_STATE_KNOWLEDGE, {})
    if (knowledge := known.get(entity_id)) is None:
        knowledge = known[entity_id] = _Knowledge()
    return knowledge


def _newest_states(
    session: Session, metadata_id: int, since: float | None
) -> tuple[set[str], bool]:
    """Return an entity's distinct states, newest first, and if that is all.

    Bounded in the query: the newest states only, through the index the
    recorder keeps on entity and time. With a `since`, only the states from
    then on. A row without a state is not read: then this is not all.
    """
    newest = select(States.state).where(States.metadata_id == metadata_id)
    if since is not None:
        newest = newest.where(States.last_updated_ts >= since)
    newest = (
        newest.order_by(States.last_updated_ts.desc())
        .limit(MOST_STATES_PER_ENTITY + 1)
        .subquery()
    )
    rows = session.execute(
        select(newest.c.state, func.count()).group_by(  # pylint: disable=not-callable
            newest.c.state
        )
    ).all()

    complete = sum(count for _state, count in rows) <= MOST_STATES_PER_ENTITY and all(
        state is not None for state, _count in rows
    )
    return {state for state, _count in rows if state is not None}, complete


def _read_recorded_states(
    hass: HomeAssistant, since_by_entity: Mapping[str, float | None]
) -> dict[str, tuple[set[str], bool]]:
    """Return the states the recorder has seen per entity.

    Runs on the recorder's executor, as one job in one session: which
    entities it knows, and the distinct states of each, bounded. Per entity
    either all of it, or only what was written since a moment.

    An entity missing from the answer was never recorded.
    """
    instance = get_instance(hass)
    with session_scope(hass=hass, read_only=True) as session:
        metadata_ids = recorder_metadata_ids(
            session, list(since_by_entity), instance.max_bind_vars
        )
        return {
            entity_id: _newest_states(session, metadata_id, since_by_entity[entity_id])
            for metadata_id, entity_id in metadata_ids.items()
        }


async def _async_ask_the_recorder(
    hass: HomeAssistant, previous_answers: dict[str, HistoryAnswer | None]
) -> None:
    """Ask the recorder about these entities, in one go, and remember it.

    An entity without a previous answer has its whole history read. One
    with an answer has only what was written since, which is added to it.
    """
    started = dt_util.utcnow()
    since_by_entity = {
        entity_id: (
            None
            if previous is None
            else (previous.read_until - NEWS_OVERLAP).timestamp()
        )
        for entity_id, previous in previous_answers.items()
    }
    try:
        recorded = await get_instance(hass).async_add_executor_job(
            _read_recorded_states, hass, since_by_entity
        )
    # A database error is logged by the recorder already. Without an answer
    # only what is certain without history gets reported.
    except SQLAlchemyError:
        LOGGER.debug(
            "Spook could not read state history for %s",
            ", ".join(previous_answers),
            exc_info=True,
        )
        return

    for entity_id, previous in previous_answers.items():
        states, complete = recorded.get(entity_id, (set(), False))
        knowledge = _knowledge(hass, entity_id)
        # Taken in before the answer is written down: these are what the
        # answer is about, not news that makes it stale.
        knowledge.seen |= states
        if previous is None:
            knowledge.answer = HistoryAnswer(
                complete=complete, asked_at=started, read_until=started
            )
        # Only added to the answer it continues. One dropped meanwhile,
        # because the entity showed something new, is read in full next time.
        elif knowledge.answer is previous:
            knowledge.answer = replace(
                previous, complete=previous.complete and complete, read_until=started
            )


@dataclass(slots=True)
class _Look:
    """One look at an entity: what it can be, and what it was asked to be."""

    state: State
    known: set[str]
    unknown: set[str]
    # Whether core writes nothing outside of what is known.
    kept: bool


async def _async_look(
    hass: HomeAssistant, entity_id: str, states: set[str]
) -> _Look | None:
    """Look at an entity as it is right now, if its states can be checked.

    What it is in and offers is noted first, so it counts from then on, also
    once it is gone again.
    """
    if (entity := _entity_object(hass, entity_id)) is None:
        return None
    if (state := hass.states.get(entity_id)) is None:
        return None

    domain = split_entity_id(entity_id)[0]
    fixed = await async_domain_states(hass, domain)
    # A domain core has an enum for, which did not come, is not checked on
    # the options alone: they never were all of it.
    if fixed is None and domain in _STATE_ENUMS:
        return None

    # Whether it is checked at all is down to what it is right now. What it
    # offered or was before only adds to what it can be: a sensor that was
    # an enum once may be a plain one now, under the same entity ID.
    offered = _offered(domain, state)
    if fixed is None and not offered:
        return None

    knowledge = _knowledge(hass, entity_id)
    knowledge.see(state.state)
    knowledge.offered |= offered

    known = {*_ALWAYS_VALID, *(fixed or ()), *knowledge.offered, *knowledge.seen}
    return _Look(
        state=state,
        known=known,
        unknown=states - known,
        kept=_set_is_kept(domain, entity),
    )


async def async_unknown_states(
    hass: HomeAssistant,
    pairs: Iterable[tuple[str, str]],
) -> set[UnknownState]:
    """Return the (entity ID, state) pairs whose entity is never in that state.

    An entity without a state is passed over: whether it exists is another
    repair's business. So is one whose states are not a fixed set, and one
    its domain did not load itself.

    Where core keeps the set, a state that differs from a known one in case
    alone is always reported: `On` next to a real `on` is never meant.
    Anything else outside of it only with the whole history, in case Spook
    reads core wrong. Where core does not keep it, only the case slip, and
    only with the whole history: such an entity can be in anything, and the
    history is all there is to say what it has been.
    """
    states_by_entity: dict[str, set[str]] = defaultdict(set)
    for entity_id, state in pairs:
        states_by_entity[entity_id].add(state)

    # Worked out from memory first: the fixed states, the options, and every
    # state ever seen. In a normal house that settles all of it.
    suspects: dict[str, _Look] = {}
    for entity_id, states in states_by_entity.items():
        if (look := await _async_look(hass, entity_id, states)) and look.unknown:
            suspects[entity_id] = look

    # What is left goes to the recorder, all of it in one go, and only for
    # entities it keeps a history of. All of the history when it has not
    # answered for a while, otherwise only what it wrote since.
    with_history = (
        {entity_id for entity_id in suspects if is_entity_recorded(hass, entity_id)}
        if recorder_can_answer(hass)
        else set()
    )
    now = dt_util.utcnow()
    if to_ask := answers_to_continue(
        {entity_id: _knowledge(hass, entity_id).answer for entity_id in with_history},
        now,
    ):
        await _async_ask_the_recorder(hass, to_ask)
        now = dt_util.utcnow()

    return await _async_findings(hass, suspects, with_history, now)


async def _async_findings(
    hass: HomeAssistant,
    suspects: dict[str, _Look],
    with_history: set[str],
    now: datetime,
) -> set[UnknownState]:
    """Return what is still unknown, looking at every suspect once more.

    Looked at again after asking: the entity may have changed meanwhile, and
    what it is in now counts as much as what it was in before.
    """
    found: set[UnknownState] = set()
    for entity_id, before in suspects.items():
        if (look := await _async_look(hass, entity_id, before.unknown)) is None:
            continue

        answer = _knowledge(hass, entity_id).answer
        # An entity that changed while the recorder was asked may have passed
        # through something the recorder has not written yet. Its history is
        # not whole this round; the next one reads what came since.
        history_is_whole = (
            entity_id in with_history
            and answer is not None
            and answer.holds(now)
            and answer.complete
            and look.state.last_updated == before.state.last_updated
        )
        folded = {candidate.casefold() for candidate in look.known}
        for state in look.unknown:
            case_slip = state.casefold() in folded
            if look.kept:
                reported = case_slip or history_is_whole
            else:
                reported = case_slip and history_is_whole

            if reported:
                found.add(
                    UnknownState(
                        entity_id=entity_id,
                        state=state,
                        suggestion=suggest_name(state, look.known),
                    )
                )

    return found
