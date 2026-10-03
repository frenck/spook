"""Spook - Your homie. Entity reference extraction from dashboard configs.

The Lovelace repair used to hand-walk a fixed set of known card shapes,
missing references in custom cards and any structure it did not explicitly
recurse into. This module walks a dashboard configuration generically: it
recurses through every container and collects entity references from
reference-shaped keys wherever they appear, so custom cards are covered
for free.

Only recognized keys are read; arbitrary strings are never collected. The
downstream ``async_filter_known_entity_ids`` still validates every value,
so a benign string under a recognized key is dropped rather than reported.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .entity_filtering import split_comma_separated_entity_ids
from .reference_extraction import is_pattern_reference

if TYPE_CHECKING:
    from collections.abc import Iterator

# Keys whose value holds one or more entity references, anywhere in a
# dashboard configuration. Values may be a single entity ID, a
# comma-separated list, or a list of entity IDs; entity IDs nested inside
# dicts (like entities-card rows) are reached by the recursion instead.
_ENTITY_REFERENCE_KEYS = frozenset(
    {
        "badges",
        "camera_image",
        "entities",
        "entity",
        "entity_id",
        "entity_ids",
        "exclude_entities",
        "favorite_entities",
        "image_entity",
        "include_entities",
    },
)


# Keys whose subtree says which entities to pick rather than naming any.
# `filter` is what auto-entities and the cards that copy it use, and what is
# under one describes a selection: a domain, an area, a state, a pattern. None
# of it names a particular entity, so reading it as a reference produces
# repairs about dashboards that work perfectly well. #1514 was `area: KG/*`,
# meaning every area under KG, reported as an area that had gone missing.
_MATCHER_KEYS = frozenset({"filter"})

# Except for this one. `options` is not a matcher: it is card configuration
# handed to whatever matched, and it can name entities of its own, a nested
# card with fixed rows among them. Those are on the dashboard and worth
# checking, so the walk goes back in there.
#
# It is also where #1468 was found, `entity: this.entity_id` standing for
# whichever entity matched. That one is turned away at the gate rather than
# here, by not being an entity anybody could have.
_NOT_A_MATCHER = "options"


def _options_within(node: Any) -> Iterator[Any]:
    """Yield the `options` blocks inside a matcher subtree."""
    if isinstance(node, list):
        for item in node:
            yield from _options_within(item)
        return

    if not isinstance(node, dict):
        return

    for key, value in node.items():
        if key == _NOT_A_MATCHER:
            if isinstance(value, (dict, list)):
                yield value
        else:
            yield from _options_within(value)


def _worth_descending_into(node: dict[str, Any]) -> Iterator[Any]:
    """Yield the subtrees of a node that can hold references."""
    for key, value in node.items():
        if key in _MATCHER_KEYS:
            yield from _options_within(value)
        elif isinstance(value, (dict, list)):
            yield value


# Placeholders a custom card hands to whatever it renders, standing for the
# row's own entity. `template-entity-row` and the Mushroom templates both use
# `config.entity`. Shaped exactly like an entity ID, so everything downstream
# takes it for one.
#
# Kept here rather than in the shared `NEVER_AN_ENTITY`, which nine repairs
# read. This is meaningless in a dashboard and could be a real dangling
# reference in a scene or a customization, and only this walk knows which it
# is looking at.
_CARD_PLACEHOLDERS = frozenset({"config.entity"})


def _collect_strings(value: Any, entities: set[str]) -> None:
    """Collect entity IDs from a recognized key's string or list value."""
    if isinstance(value, str):
        entities.update(split_comma_separated_entity_ids(value))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                entities.update(split_comma_separated_entity_ids(item))

    entities.difference_update(_CARD_PLACEHOLDERS)


# Bubble Card names entities under keys of its own. A pop-up can open on an
# entity's state (`trigger_entity`), and a horizontal buttons stack numbers its
# buttons, each with an entity and a motion sensor to sort by (`1_entity`,
# `1_pir_sensor`, and so on). Only read on Bubble Card itself: a key shaped
# like `1_entity` on some other card is that card's business.
_BUBBLE_CARD_TYPE = "custom:bubble-card"
_BUBBLE_CARD_ENTITY_KEYS = frozenset({"trigger_entity"})
_BUBBLE_CARD_NUMBERED_ENTITY_KEY = re.compile(r"\d+_(?:entity|pir_sensor)")


def _collect_bubble_card(node: dict[str, Any], entities: set[str]) -> None:
    """Collect the entities Bubble Card names under keys of its own."""
    for key, value in node.items():
        if key in _BUBBLE_CARD_ENTITY_KEYS or (
            isinstance(key, str) and _BUBBLE_CARD_NUMBERED_ENTITY_KEY.fullmatch(key)
        ):
            _collect_strings(value, entities)


def _walk(node: Any, entities: set[str]) -> None:
    """Recursively collect entity references from a configuration node."""
    if isinstance(node, list):
        for item in node:
            _walk(item, entities)
        return

    if not isinstance(node, dict):
        return

    for key in _ENTITY_REFERENCE_KEYS:
        if key in node:
            _collect_strings(node[key], entities)

    if node.get("type") == _BUBBLE_CARD_TYPE:
        _collect_bubble_card(node, entities)

    for child in _worth_descending_into(node):
        _walk(child, entities)


def extract_entities_from_dashboard_node(node: Any) -> set[str]:
    """Return the entity references found anywhere in a dashboard node.

    Accepts any part of a dashboard configuration (a whole config, a view,
    a card) and returns every entity reference reachable from it.
    """
    entities: set[str] = set()
    _walk(node, entities)
    return entities


# `area` is a reference on exactly two things, the area card and the area
# view strategy, and both say `type: area`. Anywhere else the word is up for
# grabs, and a custom card took it: flex-horseshoe-card prints whatever is
# under `area` as a caption beneath its gauge, so `area: Garaj` was reported
# as an area that had gone missing. #1609.
#
# The Mushroom template card is the exception that earns its place: its `area`
# is the card's area, handed to its templates as a real area ID.
_AREA_TYPES = frozenset({"area", "custom:mushroom-template-card"})

# `area_id` is a service-call target, and nobody captions with one of those.
_AREA_ID_KEY = "area_id"


def _collect_plain(value: Any, out: set[str]) -> None:
    """Collect plain string IDs from a key's string or list value.

    A pattern is not a name, so `area: KG/*` is left where it is. Neither is
    a template: no area ID has braces in it, and what a template turns into
    is not something to look up ahead of time.
    """
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list):
        return

    out.update(
        item
        for item in values
        if isinstance(item, str)
        and not is_pattern_reference(item)
        and not _is_template(item)
    )


def _is_template(value: str) -> bool:
    """Return whether a value is a Jinja template rather than a name."""
    return "{{" in value or "{%" in value


def _walk_areas(node: Any, areas: set[str]) -> None:
    """Recursively collect area references from a configuration node."""
    if isinstance(node, list):
        for item in node:
            _walk_areas(item, areas)
        return

    if not isinstance(node, dict):
        return

    # Checked for a string first: the walk goes into any dict in a dashboard,
    # and a `type` that is a list or a dict cannot be looked up in a set.
    if isinstance(card_type := node.get("type"), str) and card_type in _AREA_TYPES:
        _collect_plain(node.get("area"), areas)
    _collect_plain(node.get(_AREA_ID_KEY), areas)

    # The areas dashboard strategy lists area IDs to hide or order.
    if isinstance(areas_display := node.get("areas_display"), dict):
        for sub_key in ("hidden", "order"):
            _collect_plain(areas_display.get(sub_key), areas)

    for child in _worth_descending_into(node):
        _walk_areas(child, areas)


def extract_areas_from_dashboard_node(node: Any) -> set[str]:
    """Return the area references found anywhere in a dashboard node."""
    areas: set[str] = set()
    _walk_areas(node, areas)
    return areas


# The two kinds of action that call one. `call-service` is the old name for
# `perform-action`, and the frontend runs both the same way: the action named
# under `perform_action`, or failing that under `service`. Read exactly like
# that, so what is reported is what a tap would have tried to run.
_PERFORM_ACTION_TYPES = frozenset({"perform-action", "call-service"})
_PERFORM_ACTION_KEYS = ("perform_action", "service")

# Only a plain `domain.action` is a name to look up. A custom card can put a
# template there, button-card's `[[[ ... ]]]` for one, and a half-filled
# editor leaves it empty; neither is an action that went missing.
_ACTION_NAME = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+")


def _walk_actions(node: Any, actions: set[str]) -> None:
    """Recursively collect the actions a configuration node performs."""
    if isinstance(node, list):
        for item in node:
            _walk_actions(item, actions)
        return

    if not isinstance(node, dict):
        return

    # Read off the action itself rather than the key it sits under:
    # `tap_action`, `hold_action` and the rest are the frontend's, and custom
    # cards add their own names for the same shape. Checked for a string
    # first, like the area walk: a list or a dict cannot be looked up in a set.
    if (
        isinstance(action_type := node.get("action"), str)
        and action_type in _PERFORM_ACTION_TYPES
    ):
        for key in _PERFORM_ACTION_KEYS:
            if name := node.get(key):
                if isinstance(name, str) and _ACTION_NAME.fullmatch(name):
                    actions.add(name)
                break

    for child in _worth_descending_into(node):
        _walk_actions(child, actions)


def extract_actions_from_dashboard_node(node: Any) -> set[str]:
    """Return the actions performed anywhere in a dashboard node."""
    actions: set[str] = set()
    _walk_actions(node, actions)
    return actions
