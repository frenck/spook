"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.helper_integration import (
    async_remove_helper_config_entry_from_source_device,
)

from .const import CONF_HIDE_SOURCE

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


@callback
def async_get_source_entity_device_id(
    hass: HomeAssistant, entity_id: str
) -> str | None:
    """Get the entity device id."""
    registry = er.async_get(hass)

    if not (source_entity := registry.async_get(entity_id)):
        return None

    return source_entity.device_id


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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    if config_entry.version == 1:
        options = {**config_entry.options}
        if config_entry.minor_version < 2:
            # Remove the spook_inverse config entry from the source device
            if source_device_id := async_get_source_entity_device_id(
                hass, options[CONF_ENTITY_ID]
            ):
                async_remove_helper_config_entry_from_source_device(
                    hass,
                    helper_config_entry_id=config_entry.entry_id,
                    source_device_id=source_device_id,
                )
        hass.config_entries.async_update_entry(
            config_entry, options=options, minor_version=2
        )

    return True
