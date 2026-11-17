"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import script
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)

from ....action_extraction import (
    ConfigEntryFields,
    async_get_config_entry_fields,
    unknown_config_entries,
)
from ....repairs import (
    AbstractSpookEntityComponentUnknownReferencesRepair,
    format_config_entry_references,
)

if TYPE_CHECKING:
    from ....repairs import InspectedEntity


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown config entries in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_config_entry_references"
    # Which actions take a config entry changes as integrations load and
    # their actions come and go, so those are reasons to look again too.
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True

    unavailable_entity_class = script.UnavailableScriptEntity
    entity_label = "script"
    reference_label = "config_entries"
    edit_url_pattern = "/config/script/edit/{unique_id}"

    _config_entry_fields: ConfigEntryFields
    _entry_domains: dict[str, str]

    def _format_references(self, references: list[str]) -> str:
        """Return the list of config entries, saying which are of another one."""
        return format_config_entry_references(self.hass, references)

    async def _async_setup_inspection(self) -> None:
        """Cache which actions take a config entry for this inspection cycle."""
        self._config_entry_fields = await async_get_config_entry_fields(self.hass)
        # Every config entry there is, with the integration it belongs to,
        # snapshotted on the event loop, so the computation in the executor
        # can judge the entries a configuration names without reaching back.
        self._entry_domains = {
            entry.entry_id: entry.domain
            for entry in self.hass.config_entries.async_entries()
        }

    def _compute_unknown_references(self, entity: InspectedEntity) -> set[str]:
        """Return the config entries ``entity`` hands its actions that go nowhere."""
        if not (raw_config := entity.raw_config):
            return set()
        return unknown_config_entries(
            raw_config, self._config_entry_fields, self._entry_domains
        )
