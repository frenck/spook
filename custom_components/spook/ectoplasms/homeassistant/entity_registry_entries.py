"""Spook - Your homie. Shared lookups for the entity icon and alias actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from ...const import DOMAIN
from ...errors import entity_not_found

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant


@callback
def async_get_registry_entries(
    hass: HomeAssistant, entity_ids: Iterable[str]
) -> list[er.RegistryEntry]:
    """Return the registry entries for these entities, or raise for the first bad one.

    All of them are looked up before anything is changed, so a typo late in
    the list does not leave the first ones changed behind an error. An entity
    that exists without a unique ID has no registry entry, and so nothing an
    icon or alias could be kept on; that gets its own explanation.
    """
    entity_registry = er.async_get(hass)
    entries = []

    for entity_id in entity_ids:
        if (entry := entity_registry.async_get(entity_id)) is not None:
            entries.append(entry)
            continue

        if hass.states.get(entity_id) is not None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="entity_without_unique_id",
                translation_placeholders={"entity_id": entity_id},
            )

        raise entity_not_found(entity_id)

    return entries


def clean_aliases(aliases: Iterable[str]) -> list[str]:
    """Trim aliases and drop the empty ones and repeats, like core's editor does."""
    return list(dict.fromkeys(alias.strip() for alias in aliases if alias.strip()))
