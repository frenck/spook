"""Spook - Your homie. Telling an attribute an entity has from one it never had.

An attribute is only unknown when every source agrees it is: what the kind of
entity offers in Home Assistant, what every entity offers, what this entity
has right now, and what the recorder remembers it ever having. Absence from
one of those means nothing. A media player that is off drops most of its
attributes, an integration adds its own that only show up now and then.

The recorder is asked last, and only about what is left after the rest.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import timedelta
from enum import StrEnum
import importlib
import re
import sys
from typing import TYPE_CHECKING, Final

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from homeassistant.components.recorder import is_entity_recorded
from homeassistant.components.recorder.db_schema import (
    StateAttributes,
    States,
    StatesMeta,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_ENTITY_ID,
    ATTR_ID,
    MATCH_ALL,
    EntityCapabilityAttribute,
    EntityStateAttribute,
)
from homeassistant.core import split_entity_id
from homeassistant.helpers.recorder import (
    DATA_INSTANCE,
    async_migration_in_progress,
    get_instance,
    session_scope,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.collection import chunked_or_all
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import json_loads_object

from .const import LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from datetime import datetime
    from types import ModuleType

    from sqlalchemy.orm import Session

    from homeassistant.core import HomeAssistant, State

# Attributes any entity can carry, whatever its domain. Core's own list of
# them, plus the few it sets on entities of many domains without a domain
# enum saying so: `editable` on every helper, `id` on the helpers made in
# the UI, and `entity_id` on anything that has members, groups and scenes
# among them. Too many here only means Spook says less.
GENERIC_ATTRIBUTES: Final = frozenset(
    {
        *EntityStateAttribute,
        *EntityCapabilityAttribute,
        ATTR_EDITABLE,
        ATTR_ENTITY_ID,
        ATTR_ID,
    }
)

# How core names the enums of a domain's attributes. Not only
# `<Domain>EntityStateAttribute`: a capability is an attribute too, and water
# heaters and device trackers spell theirs a little differently.
_ATTRIBUTE_ENUM_SUFFIXES = ("StateAttribute", "CapabilityAttribute")

# How long a full read of an entity's history stays good. In between, only
# what the recorder wrote since the last read is read, which is a handful of
# rows at most: an attribute that came and went between two rounds counts,
# without reading everything again.
HISTORY_IS_GOOD_FOR: Final = timedelta(days=1)

# How far back from the last read the next one starts. The recorder writes in
# batches, so a state can land in the database a little after it happened.
# Reading a few rows twice costs nothing; missing one is a false finding.
NEWS_OVERLAP: Final = timedelta(minutes=10)

# How much of an entity's history is read, newest first, and bounded in the
# database itself: the most states looked at, and of the attribute sets those
# used, the most read. A sensor carrying a timestamp in its attributes has a
# new set for nearly every state, and reading all of them buys nothing: the
# keys repeat. An entity with more than either is read partially, and then
# nothing missing from it is reported, because the part not read might have
# had it.
MOST_STATES_PER_ENTITY: Final = 50_000
MOST_ATTRIBUTE_SETS_PER_ENTITY: Final = 1000

# A one-letter slip is only a slip in a name long enough to have letters to
# spare. `mode` and `node` are both real words.
_SHORTEST_NAME_TO_CORRECT = 5

_SEPARATORS = re.compile(r"[\s_-]+")

DATA_DOMAIN_ATTRIBUTES: HassKey[dict[str, frozenset[str]]] = HassKey(
    "spook_domain_attributes"
)
DATA_ATTRIBUTE_KNOWLEDGE: HassKey[dict[str, _Knowledge]] = HassKey(
    "spook_attribute_knowledge"
)


@dataclass(frozen=True, slots=True)
class UnknownAttribute:
    """An attribute somebody named that its entity does not have."""

    entity_id: str
    attribute: str
    suggestion: str | None


@dataclass(frozen=True, slots=True)
class _Answer:
    """What the recorder said about an entity, beyond the keys it showed."""

    # Whether the entity's whole history was read, so absence means
    # something. False when it was never recorded, has more than is read, or
    # has states whose attributes the recorder did not keep.
    complete: bool
    # When the whole history was read, and when anything was read last.
    asked_at: datetime
    read_until: datetime

    def holds(self, now: datetime) -> bool:
        """Return whether this is recent enough to go by."""
        return now - self.asked_at < HISTORY_IS_GOOD_FOR


@dataclass(slots=True)
class _Knowledge:
    """What Spook knows about the attributes of one entity."""

    # Every key ever seen, on the entity's state or in the recorder. Grows
    # only: an attribute that went away again, or was purged from history,
    # was still real, and is never asked about again.
    seen: set[str] = field(default_factory=set)
    answer: _Answer | None = None

    def see(self, keys: Iterable[str]) -> None:
        """Note keys the entity shows right now.

        A key not seen before means the entity changed since the recorder was
        asked, so its answer no longer tells the whole story.
        """
        if new := set(keys) - self.seen:
            self.seen |= new
            self.answer = None


def _attributes_from_module(module: ModuleType) -> frozenset[str]:
    """Return the attributes the attribute enums in a module list."""
    return frozenset(
        member.value
        for name, value in vars(module).items()
        if name.endswith(_ATTRIBUTE_ENUM_SUFFIXES)
        and isinstance(value, type)
        and issubclass(value, StrEnum)
        for member in value
    )


async def async_domain_attributes(hass: HomeAssistant, domain: str) -> frozenset[str]:
    """Return the attributes core says entities of a domain can have.

    Read live from core rather than copied, so a release adding one is
    picked up without Spook doing anything. Imported off the event loop the
    first time, and remembered per domain from then on. A domain without
    such a module, or one that fails to import, has none: that makes Spook
    say less, never more.
    """
    known = hass.data.setdefault(DATA_DOMAIN_ATTRIBUTES, {})
    if (attributes := known.get(domain)) is not None:
        return attributes

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
            LOGGER.debug("Spook found no attribute enums for %s", domain)
            module = None

    attributes = frozenset() if module is None else _attributes_from_module(module)
    known[domain] = attributes
    return attributes


def _unrecorded(state: State) -> frozenset[str]:
    """Return the attributes the recorder leaves out for this entity."""
    if not (state_info := state.state_info):
        return frozenset()
    return state_info["unrecorded_attributes"]


def _folded(name: str) -> str:
    """Return a name without case or separators."""
    return _SEPARATORS.sub("", name).casefold()


def _one_edit_apart(name: str, other: str) -> bool:
    """Return whether one insert, delete, swap or replace turns one into other."""
    if name == other or abs(len(name) - len(other)) > 1:
        return False

    if len(name) == len(other):
        differ = [
            index
            for index, (a, b) in enumerate(zip(name, other, strict=True))
            if a != b
        ]
        if len(differ) == 1:
            return True
        # Two neighbours swapped.
        return (
            len(differ) == 2  # noqa: PLR2004
            and differ[1] == differ[0] + 1
            and name[differ[0]] == other[differ[1]]
            and name[differ[1]] == other[differ[0]]
        )

    shorter, longer = sorted((name, other), key=len)
    index = 0
    while index < len(shorter) and shorter[index] == longer[index]:
        index += 1
    return shorter[index:] == longer[index + 1 :]


def suggest_attribute(name: str, known: Iterable[str]) -> str | None:
    """Return what somebody most likely meant, but only when it is near certain.

    The same name up to case and separators: `Brightness`, `color temp` and
    `colorTemp` are `brightness` and `color_temp`. Otherwise one edit away,
    for names of five characters or more, and only when exactly one attribute
    qualifies. Anything vaguer is a guess, and a wrong suggestion is worse
    than none.
    """
    known = set(known)

    folded = _folded(name)
    same = {candidate for candidate in known if _folded(candidate) == folded}
    same.discard(name)
    if same:
        return same.pop() if len(same) == 1 else None

    if len(name) < _SHORTEST_NAME_TO_CORRECT:
        return None

    close = {
        candidate
        for candidate in known
        if _one_edit_apart(name.casefold(), candidate.casefold())
    }
    return close.pop() if len(close) == 1 else None


def _metadata_ids(
    session: Session, entity_ids: list[str], max_bind_vars: int
) -> dict[int, str]:
    """Return the recorder's metadata ID of each entity it has a history of."""
    found: dict[int, str] = {}
    for chunk in chunked_or_all(entity_ids, max_bind_vars):
        rows = session.execute(
            select(StatesMeta.metadata_id, StatesMeta.entity_id).where(
                StatesMeta.entity_id.in_(chunk)
            )
        )
        found.update(dict(rows.all()))
    return found


def _newest_attribute_sets(
    session: Session, metadata_id: int, since: float | None
) -> tuple[list[int], bool]:
    """Return an entity's newest distinct attribute sets, and if that is all.

    Both bounds are in the query: the newest states only, through the index
    the recorder keeps on entity and time, and of the sets those used, the
    newest only. Neither the work nor the answer grows with history. With a
    `since`, only the states from then on.

    A state without a set of its own is from before the recorder kept them
    apart, and is not read: then this is not all.
    """
    newest = select(States.attributes_id, States.last_updated_ts).where(
        States.metadata_id == metadata_id
    )
    if since is not None:
        newest = newest.where(States.last_updated_ts >= since)
    newest = (
        newest.order_by(States.last_updated_ts.desc())
        .limit(MOST_STATES_PER_ENTITY + 1)
        .subquery()
    )
    rows = session.execute(
        select(newest.c.attributes_id, func.count())  # pylint: disable=not-callable
        .group_by(newest.c.attributes_id)
        .order_by(func.max(newest.c.last_updated_ts).desc())
        .limit(MOST_ATTRIBUTE_SETS_PER_ENTITY + 1)
    ).all()

    complete = (
        len(rows) <= MOST_ATTRIBUTE_SETS_PER_ENTITY
        and sum(count for _attributes_id, count in rows) <= MOST_STATES_PER_ENTITY
        and all(attributes_id is not None for attributes_id, _count in rows)
    )
    attribute_ids = [
        attributes_id
        for attributes_id, _count in rows[:MOST_ATTRIBUTE_SETS_PER_ENTITY]
        if attributes_id is not None
    ]
    return attribute_ids, complete


def _read_recorded_attribute_keys(
    hass: HomeAssistant, since_by_entity: Mapping[str, float | None]
) -> dict[str, tuple[set[str], bool]]:
    """Return the attribute keys the recorder has seen per entity.

    Runs on the recorder's executor, as one job in one session: which
    entities it knows, the newest attribute sets of each, bounded, and then
    the keys of those sets. Never the state rows themselves. Per entity
    either all of it, or only what was written since a moment.

    An entity missing from the answer was never recorded.
    """
    instance = get_instance(hass)
    keys_by_entity: dict[str, set[str]] = {}
    complete_entities: set[str] = set()
    # One set can be shared by several entities: the recorder stores each
    # distinct set once.
    entities_by_set: dict[int, list[str]] = defaultdict(list)

    with session_scope(hass=hass, read_only=True) as session:
        metadata_ids = _metadata_ids(
            session, list(since_by_entity), instance.max_bind_vars
        )
        for metadata_id, entity_id in metadata_ids.items():
            attribute_ids, complete = _newest_attribute_sets(
                session, metadata_id, since_by_entity[entity_id]
            )
            keys_by_entity[entity_id] = set()
            if complete:
                complete_entities.add(entity_id)
            for attributes_id in attribute_ids:
                entities_by_set[attributes_id].append(entity_id)

        for attributes_id, keys in _keys_of_sets(
            session, list(entities_by_set), instance.max_bind_vars
        ):
            for entity_id in entities_by_set[attributes_id]:
                keys_by_entity[entity_id].update(keys)
                # The recorder stores an empty set for attributes too big to
                # keep. Whatever they were, they are not in the history.
                if not keys:
                    complete_entities.discard(entity_id)

    return {
        entity_id: (keys, entity_id in complete_entities)
        for entity_id, keys in keys_by_entity.items()
    }


def _keys_of_sets(
    session: Session, attribute_ids: list[int], max_bind_vars: int
) -> Iterator[tuple[int, Iterable[str]]]:
    """Yield the keys of each stored attribute set, a chunk at a time."""
    for chunk in chunked_or_all(attribute_ids, max_bind_vars):
        rows = session.execute(
            select(StateAttributes.attributes_id, StateAttributes.shared_attrs).where(
                StateAttributes.attributes_id.in_(chunk)
            )
        )
        for attributes_id, shared_attrs in rows:
            yield attributes_id, json_loads_object(shared_attrs or "{}").keys()


def _knowledge(hass: HomeAssistant, entity_id: str) -> _Knowledge:
    """Return what Spook knows about an entity, starting from nothing."""
    known = hass.data.setdefault(DATA_ATTRIBUTE_KNOWLEDGE, {})
    if (knowledge := known.get(entity_id)) is None:
        knowledge = known[entity_id] = _Knowledge()
    return knowledge


async def _async_ask_the_recorder(
    hass: HomeAssistant, previous_answers: dict[str, _Answer | None]
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
            _read_recorded_attribute_keys, hass, since_by_entity
        )
    # A database error is logged by the recorder already; a damaged attribute
    # set is not, and fails to parse. Either way, without an answer only what
    # is certain without history gets reported.
    except SQLAlchemyError, ValueError:
        LOGGER.debug(
            "Spook could not read attribute history for %s",
            ", ".join(previous_answers),
            exc_info=True,
        )
        return

    for entity_id, previous in previous_answers.items():
        keys, complete = recorded.get(entity_id, (set(), False))
        knowledge = _knowledge(hass, entity_id)
        # Taken in before the answer is written down: these are what the
        # answer is about, not news that makes it stale.
        knowledge.seen |= keys
        if previous is None:
            knowledge.answer = _Answer(
                complete=complete, asked_at=started, read_until=started
            )
        # Only added to the answer it continues. One dropped meanwhile,
        # because the entity showed something new, is read in full next time.
        elif knowledge.answer is previous:
            knowledge.answer = replace(
                previous, complete=previous.complete and complete, read_until=started
            )


def _recorder_can_answer(hass: HomeAssistant) -> bool:
    """Return whether there is a recorder to ask, and it is not busy migrating."""
    return DATA_INSTANCE in hass.data and not async_migration_in_progress(hass)


def _history_can_tell(state: State, attribute: str) -> bool:
    """Return whether the recorder would have kept this attribute of the entity."""
    unrecorded = _unrecorded(state)
    return MATCH_ALL not in unrecorded and attribute not in unrecorded


@dataclass(slots=True)
class _Look:
    """One look at an entity: its state, what is known of it, what is not."""

    state: State
    known: set[str]
    unknown: set[str]


async def _async_look(
    hass: HomeAssistant, entity_id: str, attributes: set[str]
) -> _Look | None:
    """Look at an entity as it is right now.

    Everything it shows is noted as seen first, so it counts from then on,
    also once it is gone again.
    """
    if (state := hass.states.get(entity_id)) is None:
        return None

    knowledge = _knowledge(hass, entity_id)
    knowledge.see(state.attributes)
    known = {
        *GENERIC_ATTRIBUTES,
        *await async_domain_attributes(hass, split_entity_id(entity_id)[0]),
        *knowledge.seen,
    }
    return _Look(state=state, known=known, unknown=attributes - known)


def _worth_asking_about(hass: HomeAssistant, entity_id: str, look: _Look) -> bool:
    """Return whether the recorder can say anything about what is unknown."""
    return any(
        _history_can_tell(look.state, attribute) for attribute in look.unknown
    ) and is_entity_recorded(hass, entity_id)


async def async_unknown_attributes(
    hass: HomeAssistant,
    pairs: Iterable[tuple[str, str]],
) -> set[UnknownAttribute]:
    """Return the (entity ID, attribute) pairs whose attribute is unknown.

    An entity without a state is passed over: whether it exists is another
    repair's business, and one that is not loaded cannot say what it has.

    Without a complete history for an entity, an attribute is only reported
    when it differs from a known one in case alone. `Brightness` next to a
    real `brightness` is never meant; anything else might be an attribute
    that simply has not shown up yet.
    """
    attributes_by_entity: dict[str, set[str]] = defaultdict(set)
    for entity_id, attribute in pairs:
        attributes_by_entity[entity_id].add(attribute)

    # Worked out from memory first: the enums, the generic attributes, and
    # every key ever seen. In a normal house that settles all of it.
    suspects: dict[str, _Look] = {}
    for entity_id, attributes in attributes_by_entity.items():
        if (look := await _async_look(hass, entity_id, attributes)) and look.unknown:
            suspects[entity_id] = look

    # What is left goes to the recorder, all of it in one go, and only for
    # entities it keeps a history of, about attributes it would have kept.
    # All of the history when it has not answered for a while, otherwise only
    # what it wrote since.
    with_history = (
        {
            entity_id
            for entity_id, look in suspects.items()
            if _worth_asking_about(hass, entity_id, look)
        }
        if _recorder_can_answer(hass)
        else set()
    )
    now = dt_util.utcnow()
    if to_ask := {
        entity_id: (
            answer
            if (answer := _knowledge(hass, entity_id).answer) is not None
            and answer.holds(now)
            else None
        )
        for entity_id in sorted(with_history)
    }:
        await _async_ask_the_recorder(hass, to_ask)
        now = dt_util.utcnow()

    return await _async_findings(hass, suspects, with_history, now)


async def _async_findings(
    hass: HomeAssistant,
    suspects: dict[str, _Look],
    with_history: set[str],
    now: datetime,
) -> set[UnknownAttribute]:
    """Return what is still unknown, looking at every suspect once more.

    Looked at again after asking: the entity may have changed meanwhile, and
    what it shows now counts as much as what it showed before.
    """
    found: set[UnknownAttribute] = set()
    for entity_id, before in suspects.items():
        if (look := await _async_look(hass, entity_id, before.unknown)) is None:
            continue

        answer = _knowledge(hass, entity_id).answer
        history_is_whole = (
            entity_id in with_history
            and answer is not None
            and answer.holds(now)
            and answer.complete
        )
        folded = {candidate.casefold() for candidate in look.known}
        found.update(
            UnknownAttribute(
                entity_id=entity_id,
                attribute=attribute,
                suggestion=suggest_attribute(attribute, look.known),
            )
            for attribute in look.unknown
            if (
                attribute.casefold() in folded
                and attribute not in _unrecorded(look.state)
            )
            or (history_is_whole and _history_can_tell(look.state, attribute))
        )

    return found
