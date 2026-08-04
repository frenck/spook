"""Spook - Your homie. Human-friendly detail for unknown entity references.

Turns a flat list of unknown entity IDs into a bulleted description that,
where possible, explains why an entity is unknown: it was deleted (with
when and by which integration), or a similarly named entity exists that
was likely the intended target. Purely cosmetic; it never changes which
entities are reported.
"""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er

from .entity_filtering import async_get_all_entity_ids

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant

# Only suggest a rename when the names are quite close, to avoid pointing
# at an unrelated entity.
_RENAME_SIMILARITY_CUTOFF = 0.8


def async_describe_unknown_entities(
    hass: HomeAssistant,
    entity_ids: Iterable[str],
    *,
    note: str | None = None,
) -> str:
    """Return a bulleted, enriched description of unknown entity IDs.

    A ``note`` is appended to every line, to qualify a group of entity IDs
    that share something worth saying once per entry.
    """
    entity_registry = er.async_get(hass)
    deleted_by_entity_id = {
        deleted.entity_id: deleted
        for deleted in entity_registry.deleted_entities.values()
    }
    known_entity_ids = async_get_all_entity_ids(hass)
    suffix = f" — {note}" if note else ""

    return "\n".join(
        f"- `{entity_id}`"
        + _detail(entity_id, deleted_by_entity_id, known_entity_ids)
        + suffix
        for entity_id in entity_ids
    )


def _detail(
    entity_id: str,
    deleted_by_entity_id: dict[str, er.DeletedRegistryEntry],
    known_entity_ids: set[str],
) -> str:
    """Return the trailing detail for a single unknown entity ID."""
    if (deleted := deleted_by_entity_id.get(entity_id)) is not None:
        when = deleted.modified_at.date().isoformat()
        return f" (deleted on {when}, was provided by `{deleted.platform}`)"

    matches = difflib.get_close_matches(
        entity_id,
        known_entity_ids,
        n=1,
        cutoff=_RENAME_SIMILARITY_CUTOFF,
    )
    if matches:
        return f" (did you mean `{matches[0]}`?)"

    return ""
