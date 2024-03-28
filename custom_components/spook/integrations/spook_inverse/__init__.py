"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers import entity_registry as er

from .const import CONF_HIDE_SOURCE

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    await hass.config_entries.async_forward_entry_setups(
        entry,
        (entry.options["inverse_type"],),
    )
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry,
        (entry.options["inverse_type"],),
    )


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry, unhide the source entity."""
    registry = er.async_get(hass)
    if not entry.options[CONF_HIDE_SOURCE]:
        return
    if not (
        entity_id := er.async_resolve_entity_id(registry, entry.options[CONF_ENTITY_ID])
    ):
        return
    if (entity_entry := registry.async_get(entity_id)) is None:
        return
    if entity_entry.hidden_by != er.RegistryEntryHider.INTEGRATION:
        return

    registry.async_update_entity(entity_id, hidden_by=None)
