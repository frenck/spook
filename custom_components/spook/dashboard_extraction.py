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
# `filter` is what auto-entities and the cards that copy it use: everything
# under it is a matcher, and an `options` block inside it is card configuration
# handed to whatever matched. Neither one names a particular entity, so reading
# them as references produces repairs about dashboards that work perfectly well.
#
# Reported twice from inside the same block. #1468 was `entity: this.entity_id`
# under `options`, a placeholder for whichever entity matched. #1514 was
# `area: KG/*`, every area under KG. Both were read as things that had gone
# missing.
_MATCHER_KEYS = frozenset({"filter"})


def _worth_descending_into(node: dict[str, Any]) -> Iterator[Any]:
    """Yield the subtrees of a node that can hold references."""
    for key, value in node.items():
        if key not in _MATCHER_KEYS and isinstance(value, (dict, list)):
            yield value


def _collect_strings(value: Any, entities: set[str]) -> None:
    """Collect entity IDs from a recognized key's string or list value."""
    if isinstance(value, str):
        entities.update(split_comma_separated_entity_ids(value))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                entities.update(split_comma_separated_entity_ids(item))


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


# Keys whose value holds one or more area references. ``area`` is the area
# card and area view strategy; ``area_id`` is a service-call area target.
_AREA_REFERENCE_KEYS = frozenset({"area", "area_id"})


def _collect_plain(value: Any, out: set[str]) -> None:
    """Collect plain string IDs from a key's string or list value.

    A pattern is not a name, so `area: KG/*` is left where it is.
    """
    if isinstance(value, str):
        if not is_pattern_reference(value):
            out.add(value)
    elif isinstance(value, list):
        out.update(
            item
            for item in value
            if isinstance(item, str) and not is_pattern_reference(item)
        )


def _walk_areas(node: Any, areas: set[str]) -> None:
    """Recursively collect area references from a configuration node."""
    if isinstance(node, list):
        for item in node:
            _walk_areas(item, areas)
        return

    if not isinstance(node, dict):
        return

    for key in _AREA_REFERENCE_KEYS:
        if key in node:
            _collect_plain(node[key], areas)

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
