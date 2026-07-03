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

from typing import Any

from .entity_filtering import split_comma_separated_entity_ids

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

    for value in node.values():
        if isinstance(value, (dict, list)):
            _walk(value, entities)


def extract_entities_from_dashboard_node(node: Any) -> set[str]:
    """Return the entity references found anywhere in a dashboard node.

    Accepts any part of a dashboard configuration (a whole config, a view,
    a card) and returns every entity reference reachable from it.
    """
    entities: set[str] = set()
    _walk(node, entities)
    return entities
