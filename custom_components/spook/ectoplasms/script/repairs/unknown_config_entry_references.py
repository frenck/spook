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
    from typing import Any


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

    def _format_references(self, references: list[str]) -> str:
        """Return the list of config entries, saying which are of another one."""
        return format_config_entry_references(self.hass, references)

    async def _async_setup_inspection(self) -> None:
        """Cache which actions take a config entry for this inspection cycle."""
        self._config_entry_fields = await async_get_config_entry_fields(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return the config entries ``entity`` hands its actions that go nowhere."""
        if not (raw_config := getattr(entity, "raw_config", None)):
            return set()
        return unknown_config_entries(self.hass, raw_config, self._config_entry_fields)
