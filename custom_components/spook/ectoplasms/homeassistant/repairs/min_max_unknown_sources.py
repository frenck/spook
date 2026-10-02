"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....entity_suggestions import async_describe_unknown_entities
from ....helper_sources import async_unknown_min_max_members
from ....repairs import AbstractSpookRepair


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

            if not (unknown := async_unknown_min_max_members(self.hass, entry)):
                continue

            self.async_create_issue(
                issue_id=entry.entry_id,
                references=unknown,
                issue_domain=entry.domain,
                is_fixable=True,
                data={
                    "min_max_config_entry_id": entry.entry_id,
                    # What the fix checks again before pruning anything.
                    "min_max_unknown_sources": ",".join(sorted(unknown)),
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
