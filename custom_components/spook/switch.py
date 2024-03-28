"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .util import async_forward_platform_entry_setups_to_ectoplasm

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook switches."""
    await async_forward_platform_entry_setups_to_ectoplasm(
        hass,
        entry,
        async_add_entities,
        Platform.SWITCH,
    )
