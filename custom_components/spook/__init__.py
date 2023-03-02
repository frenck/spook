"""Spook - Not your homie. Custom integration for Home Assistant."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import EVENT_HOMEASSISTANT_STARTED

from .const import PLATFORMS
from .repairs import SpookRepairManager
from .services import SpookServiceManager

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import Event, HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up services
    services = SpookServiceManager(hass)
    await services.async_setup()
    entry.async_on_unload(services.async_on_unload)

    # Who you gonna call? SpookRepairManager!
    repairs = SpookRepairManager(hass)

    async def _ghost_busters(_: Event) -> None:
        """Send them in, time for some ghost chasing."""
        await repairs.async_setup()
        entry.async_on_unload(repairs.async_on_unload)

    # Wait until Home Assistant is started, before doing repairs
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _ghost_busters),
    )

    # Yay, we didn't got spooked!
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
