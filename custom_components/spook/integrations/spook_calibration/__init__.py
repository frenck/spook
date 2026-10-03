"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.SENSOR]


@callback
def async_source_device_id(hass: HomeAssistant, source: str) -> str | None:
    """Return the device the source entity belongs to, if any."""
    registry = er.async_get(hass)
    if not (entity_id := er.async_resolve_entity_id(registry, source)):
        return None
    if not (entry := registry.async_get(entity_id)):
        return None
    return entry.device_id


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    source = entry.options[CONF_ENTITY_ID]

    @callback
    def _follow_the_source(source_entity_id: str) -> None:
        """Keep up with the source being renamed, the way core helpers do."""
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_ENTITY_ID: source_entity_id}
        )

    # A source stored as a registry ID that is gone resolves to nothing, and
    # Home Assistant raises on following that. The sensor still sets up, and
    # waits for a source that may never come.
    if er.async_resolve_entity_id(er.async_get(hass), source):
        entry.async_on_unload(
            async_handle_source_entity_changes(
                hass,
                helper_config_entry_id=entry.entry_id,
                set_source_entity_id_or_uuid=_follow_the_source,
                source_device_id=async_source_device_id(hass, source),
                source_entity_id_or_uuid=source,
            )
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_changed))
    return True


async def _async_options_changed(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Start over with what was changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
