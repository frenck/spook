"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

# The min/max helper stores its members under this option key, as entity
# registry IDs or entity IDs (both resolved via ``er.async_resolve_entity_id``).
_ENTITY_IDS = "entity_ids"


def async_unknown_members(hass: HomeAssistant, entry: ConfigEntry) -> set[str]:
    """Return the raw member references of a min/max helper that are gone."""
    entity_registry = er.async_get(hass)
    known_entity_ids = async_get_all_entity_ids(hass)

    unknown: set[str] = set()
    for value in entry.options.get(_ENTITY_IDS) or []:
        if not isinstance(value, str):
            continue
        resolved = er.async_resolve_entity_id(entity_registry, value)
        if resolved is None:
            # A registry ID whose entry was deleted.
            unknown.add(value)
        elif async_filter_known_entity_ids(
            hass, [resolved], known_entity_ids=known_entity_ids
        ):
            unknown.add(value)
    return unknown


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds min/max helpers with members that no longer exist.

    Reads the config entry options directly (a public API). The missing
    members can be pruned, keeping the helper working on the ones that
    remain, so the issue is fixable.
    """

    domain = "homeassistant"
    repair = "min_max_unknown_sources"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = "min_max"
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        self.possible_issue_ids.clear()

        for entry in self.hass.config_entries.async_entries("min_max"):
            self.possible_issue_ids.add(entry.entry_id)

            if not (unknown := async_unknown_members(self.hass, entry)):
                continue

            self.async_create_issue(
                issue_id=entry.entry_id,
                issue_domain=entry.domain,
                is_fixable=True,
                data={
                    "min_max_config_entry_id": entry.entry_id,
                    "helper": entry.title,
                    "sources": async_describe_unknown_entities(
                        self.hass, sorted(unknown)
                    ),
                },
                translation_placeholders={
                    "helper": entry.title,
                    "sources": async_describe_unknown_entities(
                        self.hass, sorted(unknown)
                    ),
                },
            )
