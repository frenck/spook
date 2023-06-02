"""Spook - Not your homie."""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook sensors."""
    LOGGER.debug("Setting up Spook ectoplasm sensors")

    for module_file in Path(__file__).parent.rglob("ectoplasms/*/sensor.py"):
        module_path = str(module_file.relative_to(Path(__file__).parent))[:-3].replace(
            "/",
            ".",
        )
        LOGGER.debug("Loading Spook sensor from ectoplasm: %s", module_path)
        module = importlib.import_module(f".{module_path}", __package__)
        LOGGER.debug("Setting up Spook ectoplasm sensor: %s", module_path)
        await module.async_setup_entry(hass, entry, async_add_entities)
