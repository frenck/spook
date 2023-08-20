"""Spook - Not your homie."""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_forward_platform_entry_setups_to_ectoplasm(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: Platform,
) -> None:
    """Set up Spook ectoplasm platform."""
    LOGGER.debug("Setting up Spook ectoplasm platform: %s", platform)

    for module_file in Path(__file__).parent.rglob(f"ectoplasms/*/{platform}.py"):
        module_path = str(module_file.relative_to(Path(__file__).parent))[:-3].replace(
            "/",
            ".",
        )
        LOGGER.debug("Loading Spook %s from ectoplasm: %s", platform, module_path)
        module = importlib.import_module(f".{module_path}", __package__)
        LOGGER.debug("Setting up Spook ectoplasm %s: %s", platform, module_path)
        await module.async_setup_entry(hass, entry, async_add_entities)


def link_sub_integrations(hass: HomeAssistant) -> bool:
    """Link Spook sub integrations."""
    LOGGER.debug("Linking up Spook sub integrations")

    changes = False
    for manifest in Path(__file__).parent.rglob("integrations/*/manifest.json"):
        LOGGER.debug("Linking Spook sub integration: %s", manifest.parent.name)
        dest = Path(hass.config.config_dir) / "custom_components" / manifest.parent.name
        if not dest.exists():
            src = (
                Path(hass.config.config_dir)
                / "custom_components"
                / DOMAIN
                / "integrations"
                / manifest.parent.name
            )
            dest.symlink_to(src)
            changes = True
    return changes


def unlink_sub_integrations(hass: HomeAssistant) -> bool:
    """Unlink Spook sub integrations."""
    LOGGER.debug("Unlinking Spook sub integrations")
    for manifest in Path(__file__).parent.rglob("integrations/*/manifest.json"):
        LOGGER.debug("Unlinking Spook sub integration: %s", manifest.parent.name)
        dest = Path(hass.config.config_dir) / "custom_components" / manifest.parent.name
        if dest.exists():
            dest.unlink()
