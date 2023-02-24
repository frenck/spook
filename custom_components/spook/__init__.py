"""Spook - Not your homey. Custom integration for Home Assistant."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .services import SpookServiceManager


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up services
    services = SpookServiceManager(hass)
    await services.async_setup(entry)
    hass.data[DOMAIN]["service_manager"] = services

    # Yay, we didn't got spooked!
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if ret := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN]
    return ret
