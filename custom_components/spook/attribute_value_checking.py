"""Spook - Your homie. Telling a value an attribute can have from one it never has.

A state trigger or condition with an `attribute:` waits for a value of that
attribute. Only attributes whose values are a fixed set are checked: what
Home Assistant itself lists for that attribute of that kind of entity, or
the options the entity offers for it in another attribute, like the fan
modes of a climate entity next to its fan mode.

On top of that set comes every value the attribute had: right now, every
value Spook saw it have, and every value the recorder remembers.

Core keeps none of these sets. It writes whatever the integration hands
it, and every attribute can be overwritten by the integration's own extra
attributes. So, like the states core does not keep, only a value that
differs from a known one in how it is written is reported, and only when
the whole history agrees it never was that value. Case, like `Heating` for
`heating`, or YAML reading the text as something else, like `off` as a
boolean.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from enum import StrEnum
import importlib
import sys
from typing import TYPE_CHECKING, Any, Final

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
import yaml

from homeassistant.components.recorder import is_entity_recorded
from homeassistant.components.recorder.db_schema import StateAttributes
from homeassistant.core import split_entity_id
from homeassistant.helpers.recorder import get_instance, session_scope
from homeassistant.util import dt as dt_util
from homeassistant.util.collection import chunked_or_all
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import json_loads_object

from .attribute_checking import (
    NEWS_OVERLAP,
    HistoryAnswer,
    answers_to_continue,
    history_can_tell,
    newest_attribute_sets,
    recorder_can_answer,
    recorder_metadata_ids,
)
from .const import LOGGER
from .state_checking import entity_object

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

    from sqlalchemy.orm import Session

    from homeassistant.core import HomeAssistant, State

    from .reference_extraction import AttributeValue

# What a value can be compared as. Anything else an attribute holds, like a
# list, is never equal to a value written out in a trigger.
type Value = str | int | float | bool

# The attributes core lists the values of in an enum, and that enum, in the
# `const` module of the domain. The frontend's `FIXED_DOMAIN_ATTRIBUTE_STATES` says which attributes have a
# fixed set; the values are read from core, so a release adding one is picked
# up without Spook doing anything. An enum that cannot be found means the
# attribute has no fixed set, rather than one from a guess. Every one of these
# is in core from 2026.8 on.
#
# Left out of the frontend's list: a camera's `frontend_stream_type`, which
# core no longer writes. On top of it: a light's `color_mode`, for which core
# has an enum, while the frontend only offers the light's supported ones.
_VALUE_ENUMS: Final = {
    ("alarm_control_panel", "code_format"): "CodeFormat",
    ("binary_sensor", "device_class"): "BinarySensorDeviceClass",
    ("button", "device_class"): "ButtonDeviceClass",
    ("climate", "hvac_action"): "HVACAction",
    ("cover", "device_class"): "CoverDeviceClass",
    ("device_tracker", "source_type"): "SourceType",
    ("humidifier", "action"): "HumidifierAction",
    ("humidifier", "device_class"): "HumidifierDeviceClass",
    ("light", "color_mode"): "ColorMode",
    ("media_player", "device_class"): "MediaPlayerDeviceClass",
    ("media_player", "media_content_type"): "MediaType",
    ("media_player", "repeat"): "RepeatMode",
    ("number", "device_class"): "NumberDeviceClass",
    ("sensor", "device_class"): "SensorDeviceClass",
    ("sensor", "state_class"): "SensorStateClass",
    ("switch", "device_class"): "SwitchDeviceClass",
    ("update", "device_class"): "UpdateDeviceClass",
}

# The attributes of the frontend's list core has no enum for. A fan's
# direction is one of two constants, a water heater's away mode is written
# as on or off. A light's effect is whatever the light offers, plus core's
# own word for none, its `EFFECT_OFF`.
_FIXED_VALUES: Final[dict[tuple[str, str], tuple[str, ...]]] = {
    ("fan", "direction"): ("forward", "reverse"),
    ("light", "effect"): ("off",),
    ("water_heater", "away_mode"): ("on", "off"),
}

# The attribute listing the values another attribute of the same entity can
# have, from the frontend's `DOMAIN_OPTIONS_ATTRIBUTES`, each pair checked
# against what core writes. Left out: the ones about the state, which the
# state checks cover, and a cover's speed, which core never writes as an
# attribute.
_OPTIONS_ATTRIBUTES: Final = {
    ("climate", "fan_mode"): "fan_modes",
    ("climate", "preset_mode"): "preset_modes",
    ("climate", "swing_horizontal_mode"): "swing_horizontal_modes",
    ("climate", "swing_mode"): "swing_modes",
    ("event", "event_type"): "event_types",
    ("fan", "preset_mode"): "preset_modes",
    ("humidifier", "mode"): "available_modes",
    ("light", "color_mode"): "supported_color_modes",
    ("light", "effect"): "effect_list",
    ("media_player", "sound_mode"): "sound_mode_list",
    ("media_player", "source"): "source_list",
    ("remote", "current_activity"): "activity_list",
    ("vacuum", "fan_speed"): "fan_speed_list",
    ("water_heater", "operation_mode"): "operation_list",
}

# Every attribute checked, per domain: the ones history is read for.
_CHECKED: Final[dict[str, set[str]]] = defaultdict(set)
for _domain, _attribute in (*_VALUE_ENUMS, *_FIXED_VALUES, *_OPTIONS_ATTRIBUTES):
    _CHECKED[_domain].add(_attribute)

# What YAML makes of text that is not left as text. Only these are looked
# for: a value written as a boolean or a number, that was meant as text.
_YAML_RESOLVER = yaml.resolver.Resolver()
_YAML_SCALARS: Final = frozenset(
    {"tag:yaml.org,2002:bool", "tag:yaml.org,2002:float", "tag:yaml.org,2002:int"}
)

DATA_ATTRIBUTE_VALUES: HassKey[dict[tuple[str, str], frozenset[Value] | None]] = (
    HassKey("spook_attribute_values")
)
DATA_ATTRIBUTE_VALUE_KNOWLEDGE: HassKey[dict[str, _Knowledge]] = HassKey(
    "spook_attribute_value_knowledge"
)


@dataclass(frozen=True, slots=True)
class UnknownAttributeValue:
    """A value somebody named for an attribute that it never has."""

    entity_id: str
    attribute: str
    value: Value
    suggestion: str | None


def _comparable(value: Any) -> Value | None:
    """Return a value the way it is compared, or None if it never compares.

    An enum member is its text: that is what equals it.
    """
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int | float):
        return value
    return None


def _take_in(
    seen: dict[str, set[Value]], attributes: Mapping[str, Any], checked: Iterable[str]
) -> bool:
    """Add the values of the checked attributes to what was seen.

    An attribute that is there counts as had, even with nothing in it that
    compares, like nothing at all. Returns whether any of it was news.
    """
    news = False
    for attribute in checked:
        if attribute not in attributes:
            continue

        if (values := seen.get(attribute)) is None:
            values = seen[attribute] = set()
            news = True

        value = _comparable(attributes[attribute])
        if value is not None and value not in values:
            values.add(value)
            news = True
    return news


@dataclass(slots=True)
class _Knowledge:
    """What Spook knows about the checked attributes of one entity."""

    # Every value each attribute ever had, on the entity or in the recorder.
    # An attribute in here at all was there once. Grows only: a value purged
    # from history was still real.
    seen: dict[str, set[Value]] = field(default_factory=dict)
    # Every option the entity ever offered for each. Grows only too: options
    # come and go, and one gone now may well come back.
    offered: dict[str, set[str]] = field(default_factory=dict)
    answer: HistoryAnswer | None = None

    def see(self, attributes: Mapping[str, Any], checked: Iterable[str]) -> None:
        """Note the values the entity has right now.

        A value not seen before means the entity changed since the recorder
        was asked, so its answer no longer tells the whole story.
        """
        if _take_in(self.seen, attributes, checked):
            self.answer = None


async def async_fixed_values(
    hass: HomeAssistant, domain: str, attribute: str
) -> frozenset[Value] | None:
    """Return the values an attribute of a domain can have, or None if not fixed.

    Read live from core where it has an enum for them, imported off the
    event loop the first time, and remembered from then on. An enum that
    fails to import means no fixed values: that makes Spook say less.
    """
    known = hass.data.setdefault(DATA_ATTRIBUTE_VALUES, {})
    if (domain, attribute) in known:
        return known[domain, attribute]

    if (enum_name := _VALUE_ENUMS.get((domain, attribute))) is None:
        fixed = _FIXED_VALUES.get((domain, attribute))
        values = None if fixed is None else frozenset(fixed)
        known[domain, attribute] = values
        return values

    module_name = f"homeassistant.components.{domain}.const"
    if (module := sys.modules.get(module_name)) is None:
        try:
            module = await hass.async_add_import_executor_job(
                importlib.import_module, module_name
            )
        # An integration's package can fail to import in any way it likes,
        # and none of them are a reason to fail an inspection.
        # pylint: disable-next=broad-exception-caught
        except Exception:  # noqa: BLE001
            LOGGER.debug("Spook found no enum for %s of %s", attribute, domain)
            module = None

    enum = getattr(module, enum_name, None)
    values = (
        frozenset(str(member) for member in enum)
        if isinstance(enum, type) and issubclass(enum, StrEnum)
        else None
    )
    known[domain, attribute] = values
    return values


def _offered(domain: str, attribute: str, state: State) -> set[str]:
    """Return the options the entity offers for an attribute right now."""
    if (options_attribute := _OPTIONS_ATTRIBUTES.get((domain, attribute))) is None:
        return set()

    options = state.attributes.get(options_attribute)
    if not isinstance(options, list | tuple | set | frozenset):
        return set()
    return {str(option) for option in options if isinstance(option, str)}


def _knowledge(hass: HomeAssistant, entity_id: str) -> _Knowledge:
    """Return what Spook knows about an entity, starting from nothing."""
    known = hass.data.setdefault(DATA_ATTRIBUTE_VALUE_KNOWLEDGE, {})
    if (knowledge := known.get(entity_id)) is None:
        knowledge = known[entity_id] = _Knowledge()
    return knowledge


def _read_recorded_values(
    hass: HomeAssistant,
    since_by_entity: Mapping[str, float | None],
    checked_by_entity: Mapping[str, frozenset[str]],
) -> dict[str, tuple[dict[str, set[Value]], bool]]:
    """Return the values the recorder has seen of the checked attributes.

    Runs on the recorder's executor, as one job in one session, bounded the
    way the attribute checks read: the newest attribute sets of each entity,
    then the values in those. Per entity either all of it, or only what was
    written since a moment.

    An entity missing from the answer was never recorded.
    """
    instance = get_instance(hass)
    values_by_entity: dict[str, dict[str, set[Value]]] = {}
    complete_entities: set[str] = set()
    # One set can be shared by several entities: the recorder stores each
    # distinct set once.
    entities_by_set: dict[int, list[str]] = defaultdict(list)

    with session_scope(hass=hass, read_only=True) as session:
        metadata_ids = recorder_metadata_ids(
            session, list(since_by_entity), instance.max_bind_vars
        )
        for metadata_id, entity_id in metadata_ids.items():
            attribute_ids, complete = newest_attribute_sets(
                session, metadata_id, since_by_entity[entity_id]
            )
            values_by_entity[entity_id] = {}
            if complete:
                complete_entities.add(entity_id)
            for attributes_id in attribute_ids:
                entities_by_set[attributes_id].append(entity_id)

        for attributes_id, attributes in _attribute_sets(
            session, list(entities_by_set), instance.max_bind_vars
        ):
            for entity_id in entities_by_set[attributes_id]:
                # The recorder stores an empty set for attributes too big to
                # keep. Whatever they were, they are not in the history.
                if not attributes:
                    complete_entities.discard(entity_id)
                _take_in(
                    values_by_entity[entity_id],
                    attributes,
                    checked_by_entity[entity_id],
                )

    return {
        entity_id: (values, entity_id in complete_entities)
        for entity_id, values in values_by_entity.items()
    }


def _attribute_sets(
    session: Session, attribute_ids: list[int], max_bind_vars: int
) -> Iterable[tuple[int, dict[str, Any]]]:
    """Yield each stored attribute set, a chunk at a time."""
    for chunk in chunked_or_all(attribute_ids, max_bind_vars):
        rows = session.execute(
            select(StateAttributes.attributes_id, StateAttributes.shared_attrs).where(
                StateAttributes.attributes_id.in_(chunk)
            )
        )
        for attributes_id, shared_attrs in rows:
            yield attributes_id, json_loads_object(shared_attrs or "{}")


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
    checked_by_entity = {
        entity_id: frozenset(_CHECKED.get(split_entity_id(entity_id)[0], ()))
        for entity_id in previous_answers
    }
    try:
        recorded = await get_instance(hass).async_add_executor_job(
            _read_recorded_values, hass, since_by_entity, checked_by_entity
        )
    # A database error is logged by the recorder already; a damaged attribute
    # set is not, and fails to parse. Either way, without an answer nothing
    # gets reported: every finding here needs the whole history.
    except SQLAlchemyError, ValueError:
        LOGGER.debug(
            "Spook could not read attribute value history for %s",
            ", ".join(previous_answers),
            exc_info=True,
        )
        return

    for entity_id, previous in previous_answers.items():
        values, complete = recorded.get(entity_id, ({}, False))
        knowledge = _knowledge(hass, entity_id)
        # Taken in before the answer is written down: these are what the
        # answer is about, not news that makes it stale.
        for attribute, recorded_values in values.items():
            knowledge.seen.setdefault(attribute, set()).update(recorded_values)
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
    """One look at an entity: what its attributes can be, what they were asked."""

    state: State
    known: dict[str, set[Value]]
    unknown: set[AttributeValue]


async def _async_look(
    hass: HomeAssistant, entity_id: str, asked: set[AttributeValue]
) -> _Look | None:
    """Look at an entity as it is right now, if any of it can be checked.

    What it has and offers is noted first, so it counts from then on, also
    once it is gone again.
    """
    if entity_object(hass, entity_id) is None:
        return None
    if (state := hass.states.get(entity_id)) is None:
        return None

    domain = split_entity_id(entity_id)[0]
    knowledge = _knowledge(hass, entity_id)
    knowledge.see(state.attributes, _CHECKED.get(domain, ()))

    known: dict[str, set[Value]] = {}
    for attribute in {asked_value.attribute for asked_value in asked}:
        fixed = await async_fixed_values(hass, domain, attribute)
        # Whether it is checked at all is down to what it is right now.
        # Options offered before only add to what it can be.
        offered = _offered(domain, attribute, state)
        if fixed is None and not offered:
            continue

        knowledge.offered.setdefault(attribute, set()).update(offered)
        known[attribute] = {
            *(fixed or ()),
            *knowledge.offered[attribute],
            *knowledge.seen.get(attribute, ()),
        }

    return _Look(
        state=state,
        known=known,
        unknown={
            asked_value
            for asked_value in asked
            if asked_value.attribute in known
            and asked_value.value not in known[asked_value.attribute]
        },
    )


def _yaml_reads(text: str) -> Value:
    """Return what YAML makes of text written out without quotes.

    Only a boolean or a number is made of it; anything else stays the text.
    """
    if _YAML_RESOLVER.resolve(yaml.ScalarNode, text, (True, False)) in _YAML_SCALARS:
        return yaml.safe_load(text)
    return text


def _written_as(value: Value, known: set[Value]) -> set[str]:
    """Return the known values the same as this one but for how it is written.

    Text in another case, or text that YAML read as a boolean or a number
    because it had no quotes. A number is never a slip of another number.
    """
    texts = {candidate for candidate in known if isinstance(candidate, str)}
    if isinstance(value, str):
        folded = value.casefold()
        return {text for text in texts if text.casefold() == folded}

    # True equals 1 to Python, but YAML never reads `on` as 1.
    return {
        text
        for text in texts
        if type(read := _yaml_reads(text)) is type(value) and read == value
    }


def _suggestion(written_as: set[str]) -> str | None:
    """Return what was most likely meant, when there is only one."""
    if len(written_as) != 1:
        return None

    meant = next(iter(written_as))
    # In quotes whenever YAML would not leave the meant text as text: without
    # them, YAML makes the same mistake again. `Off` in quotes is text, but
    # the `off` it was meant to be is not, unquoted.
    return meant if isinstance(_yaml_reads(meant), str) else f'"{meant}"'


async def async_unknown_attribute_values(
    hass: HomeAssistant,
    pairs: Iterable[tuple[str, AttributeValue]],
) -> set[UnknownAttributeValue]:
    """Return the (entity ID, attribute value) pairs the attribute never has.

    An entity without a state is passed over, and so is one its domain did
    not load itself, and an attribute whose values are not a fixed set.

    Only a value that differs from a known one in how it is written is
    reported, and only with the whole history of an entity that had the
    attribute. One it never had at all is the business of the unknown
    attribute repairs.
    """
    asked_by_entity: dict[str, set[AttributeValue]] = defaultdict(set)
    for entity_id, value in pairs:
        asked_by_entity[entity_id].add(value)

    # Worked out from memory first: the fixed values, the options, and every
    # value ever seen. In a normal house that settles all of it.
    suspects: dict[str, _Look] = {}
    for entity_id, asked in asked_by_entity.items():
        if (look := await _async_look(hass, entity_id, asked)) and look.unknown:
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
) -> set[UnknownAttributeValue]:
    """Return what is still unknown, looking at every suspect once more.

    Looked at again after asking: the entity may have changed meanwhile, and
    what it has now counts as much as what it had before.
    """
    found: set[UnknownAttributeValue] = set()
    for entity_id, before in suspects.items():
        if (look := await _async_look(hass, entity_id, before.unknown)) is None:
            continue

        knowledge = _knowledge(hass, entity_id)
        answer = knowledge.answer
        # An entity that changed while the recorder was asked may have passed
        # through something the recorder has not written yet. Its history is
        # not whole this round; the next one reads what came since.
        if not (
            entity_id in with_history
            and answer is not None
            and answer.holds(now)
            and answer.complete
            and look.state.last_updated == before.state.last_updated
        ):
            continue

        for asked_value in look.unknown:
            attribute = asked_value.attribute
            # Never there at all, or left out by the recorder: then there is
            # no history of its values to go by.
            if attribute not in knowledge.seen or not history_can_tell(
                look.state, attribute
            ):
                continue

            if written_as := _written_as(asked_value.value, look.known[attribute]):
                found.add(
                    UnknownAttributeValue(
                        entity_id=entity_id,
                        attribute=attribute,
                        value=asked_value.value,
                        suggestion=_suggestion(written_as),
                    )
                )

    return found
