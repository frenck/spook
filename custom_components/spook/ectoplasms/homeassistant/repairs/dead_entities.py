"""Spook - Your homie."""

from __future__ import annotations

from collections import defaultdict

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_RESTORED, EVENT_COMPONENT_LOADED, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....repairs import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds registered entities that no longer exist.

    A registry entry whose integration loaded but never provided the
    entity this session gets a restored ``unavailable`` state. Grouped per
    config entry, and only for config entries that finished loading, so a
    slow or retrying integration is never mistaken for a dead entity.
    """

    domain = "homeassistant"
    repair = "dead_entities"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        entity_registry = er.async_get(self.hass)

        dead_by_entry: dict[str, list[str]] = defaultdict(list)
        for state in self.hass.states.async_all():
            if state.state != STATE_UNAVAILABLE or not state.attributes.get(
                ATTR_RESTORED
            ):
                continue
            entry = entity_registry.async_get(state.entity_id)
            if entry is None or entry.config_entry_id is None:
                # Only config-entry-backed entities can be confirmed dead by
                # cross-checking their config entry's load state.
                continue
            dead_by_entry[entry.config_entry_id].append(state.entity_id)

        for entry_id, entity_ids in dead_by_entry.items():
            config_entry = self.hass.config_entries.async_get_entry(entry_id)
            if (
                config_entry is None
                or config_entry.state is not ConfigEntryState.LOADED
            ):
                # The integration is gone or still (re)loading; its entities
                # may still appear, so this is not a dead-entity signal.
                continue

            self.possible_issue_ids.add(entry_id)
            self.async_create_issue(
                issue_id=entry_id,
                issue_domain=config_entry.domain,
                translation_placeholders={
                    "integration": config_entry.title,
                    "entities": "\n".join(
                        f"- `{entity_id}`" for entity_id in sorted(entity_ids)
                    ),
                },
            )
