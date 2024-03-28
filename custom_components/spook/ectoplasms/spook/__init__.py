"""Spook - Not your homie."""


from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .storage import STORAGE_KEY, SpookKeyValueStore


async def async_setup_entry(hass: HomeAssistant, _: ConfigEntry) -> bool:
    """Set up the Spook ectoplasm."""
    # Initialize the Spook key/value store.
    store = SpookKeyValueStore(hass)
    await store.async_initialize()
    hass.data[STORAGE_KEY] = store

    return True
