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

from .entity_filtering import (
    async_get_all_entity_ids_by_domain,
    async_get_deleted_entities,
    async_get_rename_suggestion_cache,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er

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
    deleted_by_entity_id = async_get_deleted_entities(hass)
    known_by_domain = async_get_all_entity_ids_by_domain(hass)
    suggestions = async_get_rename_suggestion_cache(hass)
    # Parenthesized, like the deleted-on and did-you-mean details below.
    suffix = f" ({note})" if note else ""

    return "\n".join(
        f"- `{entity_id}`"
        + _detail(entity_id, deleted_by_entity_id, known_by_domain, suggestions)
        + suffix
        for entity_id in entity_ids
    )


def _detail(
    entity_id: str,
    deleted_by_entity_id: dict[str, er.DeletedRegistryEntry],
    known_by_domain: dict[str, list[str]],
    suggestions: dict[str, str | None],
) -> str:
    """Return the trailing detail for a single unknown entity ID."""
    if (deleted := deleted_by_entity_id.get(entity_id)) is not None:
        when = deleted.modified_at.date().isoformat()
        return f" (deleted on {when}, was provided by `{deleted.platform}`)"

    if (match := _rename_suggestion(entity_id, known_by_domain, suggestions)) is None:
        return ""

    return f" (did you mean `{match}`?)"


def _rename_suggestion(
    entity_id: str,
    known_by_domain: dict[str, list[str]],
    suggestions: dict[str, str | None],
) -> str | None:
    """Return a similarly named known entity ID, if one is close enough.

    Only entities in the same domain are considered. A rename that crossed
    domains is not a rename, and comparing against every entity in the
    instance is what made this expensive.
    """
    if entity_id in suggestions:
        return suggestions[entity_id]

    suggestions[entity_id] = _closest_known_entity_id(entity_id, known_by_domain)

    return suggestions[entity_id]


def _closest_known_entity_id(
    entity_id: str,
    known_by_domain: dict[str, list[str]],
) -> str | None:
    """Return the known entity ID most like this one, if any is close enough."""
    domain = entity_id.split(".", 1)[0]
    matches = difflib.get_close_matches(
        entity_id,
        known_by_domain.get(domain, ()),
        n=1,
        cutoff=_RENAME_SIMILARITY_CUTOFF,
    )
    return matches[0] if matches else None


def _work_out_suggestions(
    entity_ids: list[str],
    known_by_domain: dict[str, list[str]],
) -> dict[str, str | None]:
    """Work out a suggestion for each entity ID. Runs in an executor thread."""
    return {
        entity_id: _closest_known_entity_id(entity_id, known_by_domain)
        for entity_id in entity_ids
    }


async def async_warm_rename_suggestions(
    hass: HomeAssistant,
    entity_ids: Iterable[str],
) -> None:
    """Work out the rename suggestions for these entity IDs ahead of time.

    Every suggestion is a fuzzy comparison against every entity in its domain,
    and a house with a lot of broken references has a lot of them to do. Left
    where it used to be, inline in building one issue description after
    another, that is tens of seconds during which Home Assistant does nothing
    else at all, and a repair inspection is not worth an unresponsive house.
    So it goes to a thread, in one hop for the whole round. #1667.

    Only the comparing moves. What comes back is the same answer the inline
    version gave, and anything still missing from the cache afterwards is
    worked out where it always was, on the event loop. Which is the one
    outcome worth avoiding, so nothing here returns without filling the cache.
    """
    deleted_by_entity_id = async_get_deleted_entities(hass)
    suggestions = async_get_rename_suggestion_cache(hass)

    # Deleted entities never reach the comparison: Spook has something better
    # to say about those, and says it instead.
    missing = [
        entity_id
        for entity_id in entity_ids
        if entity_id not in suggestions and entity_id not in deleted_by_entity_id
    ]
    if not missing:
        return

    # Handed to the thread as it is. The cache rebuilds this rather than
    # changing it in place, so the thread keeps reading the version it was
    # given even if the house replaces it mid-round.
    known_by_domain = async_get_all_entity_ids_by_domain(hass)

    worked_out = await hass.async_add_executor_job(
        _work_out_suggestions, missing, known_by_domain
    )

    # Written into whatever cache is there now, which may not be the one these
    # were worked out against: an entity registering during those seconds
    # throws the old one away. They go in anyway. A suggestion made against a
    # house half a minute out of date is the same cosmetic staleness this
    # already accepts for entities that never reach the registry, and the
    # alternative is leaving the cache empty for the caller that is about to
    # describe these, which sends every one of them through the comparison
    # again on the event loop. That is the stall, not the stale sentence.
    async_get_rename_suggestion_cache(hass).update(worked_out)
