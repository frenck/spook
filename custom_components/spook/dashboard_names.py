"""Spook - Your homie. The attributes and states a dashboard names, and of what.

The same question the automation repairs ask, asked of a dashboard: which
attribute of which entity does it read, and which state of which entity does
it compare with. Only where the frontend itself does that, read the way the
frontend reads it. A card that shows nothing because it compares with a state
its entity is never in looks exactly like a card that is waiting, so nothing
else ever tells.

Some of what a dashboard names applies to more than one entity at once: the
filter of an entity filter card is held against every entity it lists. A
filter like that is fine as long as one of them can pass it, so those come
back as a group, reported only when every entity in it is found wanting.

Never judged: custom cards and everything inside them, which can mean
anything by any key, anything with a template or a placeholder in it, and
any condition whose entity the frontend works out in a way Spook cannot
follow for sure.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING, Any

from homeassistant.core import valid_entity_id

from .reference_extraction import (
    _attribute_reference,
    _is_literal_attribute,
    _state_reference,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

type Pair = tuple[str, str]
type Group = frozenset[Pair]


@dataclass(frozen=True, slots=True)
class DashboardNames:
    """The attributes and states a dashboard names, in groups.

    A group is reported only when every pair in it is unknown. Most groups
    hold one pair; the filter of an entity filter card holds one per entity.
    """

    attributes: frozenset[Group] = frozenset()
    states: frozenset[Group] = frozenset()

    @property
    def pairs(self) -> frozenset[Pair]:
        """Return every pair named, attributes and states alike."""
        return frozenset(
            pair for group in self.attributes | self.states for pair in group
        )


@dataclass(slots=True)
class _Found:
    """What the walk found so far."""

    attributes: set[Group] = field(default_factory=set)
    states: set[Group] = field(default_factory=set)

    def add(self, kind: str, group: Iterable[Pair]) -> None:
        """Add a group of pairs, if there is anything in it."""
        if group := frozenset(group):
            getattr(self, kind).add(group)


_ATTRIBUTES = "attributes"
_STATES = "states"

# A custom card is whatever its author made it. Its keys can look like the
# frontend's and mean something else entirely, so nothing in it is judged.
_CUSTOM_PREFIX = "custom:"

# Templates of any kind: Jinja's, button-card's `[[[ ]]]` and the `${ }` of
# the cards that run JavaScript. What they end up as is not known up front.
_PLACEHOLDERS = ("{", "[[", "${")

# What `||` in JavaScript passes over. A condition naming its entity as one
# of these falls through to the next way of finding it.
_JAVASCRIPT_FALSY = (None, "", 0, False)

# The frontend's own test for an entity ID, `^(\w+)\.(\w+)$` in JavaScript,
# where `\w` is ASCII only. A state value shaped like it is compared with the
# state of that entity as well, whatever its domain, so it is not a state
# anybody wrote out.
_FRONTEND_ENTITY_ID = re.compile(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+")

_LOGICAL_CONDITIONS = frozenset({"and", "or", "not"})
_STATE_CONDITIONS = frozenset({"state", "numeric_state"})


def _is_placeholder(value: str) -> bool:
    """Return whether a value is worked out while running."""
    return any(marker in value for marker in _PLACEHOLDERS)


def _entity(value: Any) -> str | None:
    """Return the value if it is one entity ID, written out."""
    if isinstance(value, str) and valid_entity_id(value):
        return value
    return None


def _name(value: Any) -> str | None:
    """Return the value if it is a name written out, rather than worked out."""
    if isinstance(value, str) and value and not _is_placeholder(value):
        return value
    return None


def _condition_entity(condition: dict[str, Any], context: str | None) -> str | None:
    """Return the entity a state condition is about, the way the frontend finds it.

    `entity_id`, then `entity`, then the card's own entity. Old frontends did
    not read `entity_id` at all, so a condition with both, naming two different
    entities, is about either one depending on who looks: not judged.
    """
    named = [
        value
        for key in ("entity_id", "entity")
        if (value := condition.get(key)) not in _JAVASCRIPT_FALSY
    ]
    if not named:
        return context
    if len(named) > 1 and named[0] != named[1]:
        return None
    return _entity(named[0])


def _compared_states(condition: dict[str, Any]) -> Any:
    """Return what a state condition compares with: `state ?? state_not`."""
    if (state := condition.get("state")) is not None:
        return state
    return condition.get("state_not")


def _leaf_names(
    condition: dict[str, Any], kind: str, entity_id: str
) -> Iterator[tuple[str, str]]:
    """Yield what one state or numeric state condition names, by kind.

    Put in core's shape and read by the automation readers, so what counts
    as a written out attribute or state is the same everywhere. On top of
    that: the frontend compares a state with the state of any entity it is
    shaped like, so none of those are taken as a state.
    """
    as_core = {
        "condition": kind,
        "entity_id": entity_id,
        "state": _compared_states(condition),
    }
    if "attribute" in condition:
        as_core["attribute"] = condition["attribute"]

    if (reference := _attribute_reference(as_core)) is not None:
        attribute = reference[1]
        if _is_literal_attribute(attribute) and _name(attribute):
            yield _ATTRIBUTES, attribute

    if kind != "state" or (reference := _state_reference(as_core)) is None:
        return

    for state in reference[1]:
        if _name(state) and not _FRONTEND_ENTITY_ID.fullmatch(state):
            yield _STATES, state


def _condition_leaves(
    conditions: Any, context: str | None
) -> Iterator[tuple[int, str, str, str]]:
    """Yield each condition's leaf, kind, entity ID and name.

    The leaf is the condition itself, by identity, so the same condition held
    against several entities can be told apart from another one.
    """
    items = conditions if isinstance(conditions, list) else [conditions]
    for condition in items:
        if not isinstance(condition, dict):
            continue

        # Switched off is not looked at, by core or the frontend. One that a
        # template switches on or off is only known to core.
        if condition.get("enabled", True) is not True:
            continue

        # Without `condition` it is the old shape of a state condition.
        kind = condition.get("condition", "state")
        if not isinstance(kind, str):
            continue
        if kind in _LOGICAL_CONDITIONS:
            yield from _condition_leaves(condition.get("conditions"), context)
            continue
        if kind not in _STATE_CONDITIONS:
            continue

        if (entity_id := _condition_entity(condition, context)) is None:
            continue
        for name_kind, name in _leaf_names(condition, kind, entity_id):
            yield id(condition), name_kind, entity_id, name


def _add_conditions(found: _Found, conditions: Any, contexts: list[str | None]) -> None:
    """Add what conditions name, held against each of these entities.

    One context is a card's own entity, or none at all. More than one is a
    filter held against every entity listed, and then each condition is one
    group across all of them.
    """
    groups: dict[tuple[int, str, str], set[Pair]] = defaultdict(set)
    for context in contexts:
        for leaf, kind, entity_id, name in _condition_leaves(conditions, context):
            groups[leaf, kind, name].add((entity_id, name))

    for (_, kind, _), pairs in groups.items():
        found.add(kind, pairs)


def _looks_numeric(value: str) -> bool:
    """Return whether JavaScript might read a value as a number.

    The entity filter compares two numbers as numbers, so `"1.0"` matches a
    state of `1`. Generous on purpose: anything Python reads as a number, and
    the spellings only JavaScript does.
    """
    text = value.strip().lower()
    if text.startswith(("0x", "0o", "0b")) or text.lstrip("+-") == "infinity":
        return True
    try:
        float(text)
    except ValueError:
        return False
    return True


# The state filter operators that compare a state as it is written out. `in`
# with text is a substring check, `"on,off"` matches `n,o`, so only its list
# form counts. The rest compare by order or pattern.
_EQUALITY_OPERATORS = frozenset({"==", "!="})
_MEMBERSHIP_OPERATORS = frozenset({"in", "not in"})


def _state_filter_names(state_filter: Any) -> Iterator[tuple[int, str, str]]:
    """Yield each filter of an entity filter's `state_filter`, kind and name.

    A filter is text or a number, compared with the state, or a mapping with
    an `operator`, a `value` and perhaps an `attribute`, whose value is then
    compared instead. See `evaluateStateFilter` in the frontend.
    """
    if not isinstance(state_filter, list):
        return

    for index, item in enumerate(state_filter):
        if isinstance(item, str):
            if (state := _name(item)) and not _looks_numeric(state):
                yield index, _STATES, state
            continue
        if not isinstance(item, dict):
            continue

        if "attribute" in item:
            if attribute := _name(item["attribute"]):
                yield index, _ATTRIBUTES, attribute
            continue

        for state in _compared_values(item):
            if (state := _name(state)) and not _looks_numeric(state):
                yield index, _STATES, state


def _compared_values(state_filter: dict[str, Any]) -> list[Any]:
    """Return what a state filter compares the state with, written out."""
    operator, value = state_filter.get("operator"), state_filter.get("value")
    if operator in _EQUALITY_OPERATORS:
        return [value]
    if operator in _MEMBERSHIP_OPERATORS and isinstance(value, list):
        return value
    return []


def _add_state_filter(found: _Found, state_filter: Any, contexts: list[str]) -> None:
    """Add what a `state_filter` names, held against each of these entities."""
    groups: dict[tuple[int, str, str], set[Pair]] = defaultdict(set)
    for context in contexts:
        for index, kind, name in _state_filter_names(state_filter):
            groups[index, kind, name].add((context, name))

    for (_, kind, _), pairs in groups.items():
        found.add(kind, pairs)


def _filters_applied(
    entity_config: dict[str, Any], card: dict[str, Any], *, conditions_first: bool
) -> tuple[str, Any] | None:
    """Return which filter an entity filter applies to one of its entities.

    The card and the badge pick differently when an entity has a state filter
    of its own while conditions apply to it as well: the card takes the state
    filter, the badge the conditions.
    """
    conditions = entity_config.get("conditions") or card.get("conditions")
    own_state_filter = entity_config.get("state_filter")
    state_filter = own_state_filter or card.get("state_filter")

    if conditions and (conditions_first or not own_state_filter):
        return "conditions", conditions
    if state_filter:
        return "state_filter", state_filter
    return None


def _add_entity_filter(found: _Found, node: dict[str, Any]) -> None:
    """Add what an entity filter card or badge holds its entities against.

    Each entity gets its own filter, or the one the card has for all of them.
    When the card and the badge would filter an entity differently, neither
    filter is judged: which one applies depends on which of the two this is.
    """
    if not isinstance(entities := node.get("entities"), list):
        return

    applied_to: dict[int, tuple[str, Any, list[str]]] = {}
    unjudged: set[int] = set()
    for item in entities:
        entity_config = item if isinstance(item, dict) else {"entity": item}
        # The frontend leaves out any entity it has no state for before
        # filtering, so one that is not an entity ID is never filtered.
        if (entity_id := _entity(entity_config.get("entity"))) is None:
            continue

        as_card = _filters_applied(entity_config, node, conditions_first=False)
        as_badge = _filters_applied(entity_config, node, conditions_first=True)
        if as_card != as_badge:
            unjudged.update(id(chosen[1]) for chosen in (as_card, as_badge) if chosen)
            continue
        if as_card is None:
            continue

        kind, filters = as_card
        applied_to.setdefault(id(filters), (kind, filters, []))[2].append(entity_id)

    for filters_id, (kind, filters, contexts) in applied_to.items():
        if filters_id in unjudged:
            continue
        if kind == "conditions":
            _add_conditions(found, filters, list(contexts))
        else:
            _add_state_filter(found, filters, contexts)


# Cards and elements with an image that changes with the state of their
# entity: `state_image` picks the image, `state_filter` a CSS filter for it,
# each keyed by state. See `hui-image`.
_PICTURE_TYPES = frozenset(
    {"picture-entity", "picture-glance", "picture-elements", "image"}
)
_STATE_KEYED = ("state_image", "state_filter")

# Where `attribute` is the attribute of the node's own entity that is shown:
# the entity and gauge cards, the attribute row and the state label element.
_ATTRIBUTE_TYPES = frozenset({"entity", "gauge", "attribute", "state-label"})

# `state_content` lists what the tile card and the entity badges show. What
# is not one of these words is the name of an attribute. See `state-display`.
# Taken whatever the domain: `remaining_time` is only special on a timer, but
# reading it as a word everywhere only means saying less.
_STATE_CONTENT_TYPES = frozenset({"tile", "entity", None})
_STATE_CONTENT_WORDS = frozenset(
    {
        "area_name",
        "device_name",
        "entity-id",
        "floor_name",
        "install_status",
        "last-changed",
        "last-updated",
        "last_changed",
        "last_triggered",
        "last_updated",
        "name",
        "parent_device_name",
        "remaining_time",
        "state",
    }
)


def _add_own_entity_names(
    found: _Found, node: dict[str, Any], node_type: Any, entity_id: str
) -> None:
    """Add what a card, badge, row or element names of its own entity."""
    if node_type in _ATTRIBUTE_TYPES and (attribute := _name(node.get("attribute"))):
        found.add(_ATTRIBUTES, [(entity_id, attribute)])

    if node_type in _STATE_CONTENT_TYPES:
        content = node.get("state_content")
        for item in content if isinstance(content, list) else [content]:
            if (attribute := _name(item)) and attribute not in _STATE_CONTENT_WORDS:
                found.add(_ATTRIBUTES, [(entity_id, attribute)])

    if node_type in _PICTURE_TYPES:
        for key in _STATE_KEYED:
            if isinstance(by_state := node.get(key), dict):
                for state in by_state:
                    if state := _name(state):
                        found.add(_STATES, [(entity_id, state)])


def _add_listed_attributes(found: _Found, node: dict[str, Any], node_type: Any) -> None:
    """Add the attributes the entities of a picture glance or map card show.

    The map only shows its `attribute` when told to label with it.
    """
    if node_type not in ("picture-glance", "map"):
        return
    if not isinstance(entities := node.get("entities"), list):
        return

    for item in entities:
        if (
            not isinstance(item, dict)
            or (entity_id := _entity(item.get("entity"))) is None
        ):
            continue
        if node_type == "map" and item.get("label_mode") != "attribute":
            continue
        if attribute := _name(item.get("attribute")):
            found.add(_ATTRIBUTES, [(entity_id, attribute)])


def _collect(
    node: dict[str, Any], node_type: Any, found: _Found, *, is_section: bool
) -> None:
    """Collect what one dashboard node names, leaving what it holds."""
    # A card or badge hands its own entity to its visibility conditions. A
    # section has none to hand, whatever it says.
    own_entity = None if is_section else _entity(node.get("entity"))

    if isinstance(visibility := node.get("visibility"), list):
        _add_conditions(found, visibility, [own_entity])

    # The conditional card, row and element hand nothing to theirs.
    if node_type == "conditional":
        _add_conditions(found, node.get("conditions"), [None])

    if node_type == "entity-filter":
        _add_entity_filter(found, node)

    if own_entity is not None:
        _add_own_entity_names(found, node, node_type, own_entity)

    _add_listed_attributes(found, node, node_type)


def _walk(node: Any, found: _Found, *, is_section: bool = False) -> None:
    """Collect what a dashboard node names, and everything under it."""
    if isinstance(node, list):
        for item in node:
            _walk(item, found, is_section=is_section)
        return

    if not isinstance(node, dict):
        return

    node_type = node.get("type")
    if isinstance(node_type, str) and node_type.startswith(_CUSTOM_PREFIX):
        return

    _collect(node, node_type, found, is_section=is_section)

    for key, value in node.items():
        # A strategy stores options for cards it makes, not cards.
        if key == "strategy":
            continue
        if isinstance(value, (dict, list)):
            _walk(value, found, is_section=key == "sections")


def extract_names_from_dashboard_node(node: Any) -> DashboardNames:
    """Return the attributes and states named anywhere in a dashboard node.

    Takes any part of a dashboard: a whole one, a view, a card.
    """
    found = _Found()
    _walk(node, found)
    return DashboardNames(
        attributes=frozenset(found.attributes), states=frozenset(found.states)
    )


def reported(groups: Iterable[Group], unknown: Iterable[Pair]) -> set[Pair]:
    """Return the pairs of every group that is unknown through and through."""
    unknown = set(unknown)
    return {pair for group in groups if group <= unknown for pair in group}
