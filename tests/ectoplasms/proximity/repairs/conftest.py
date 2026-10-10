"""Shared setup for the proximity repair tests."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.proximity.const import (
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
)
from homeassistant.const import CONF_ZONE
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_set_up_proximity(
    hass: HomeAssistant,
    *,
    zone: str = "zone.home",
    tracked: list[str] | None = None,
    ignored_zones: list[str] | None = None,
) -> ConfigEntry:
    """Set up a real proximity config entry.

    Set up rather than faked, because what these repairs read is exactly the
    thing a fake would have to guess at: proximity keeps its coordinator on
    the config entry, and only a loaded entry has one.
    """
    assert await async_setup_component(hass, "zone", {})
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain="proximity",
        title="Home",
        data={
            CONF_ZONE: zone,
            CONF_TRACKED_ENTITIES: tracked if tracked is not None else [],
            CONF_IGNORED_ZONES: ignored_zones if ignored_zones is not None else [],
            CONF_TOLERANCE: 1,
        },
        unique_id="home",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
