"""Spook - Your homie. Ectoplasm setup forwarding helpers."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from .const import LOGGER

if TYPE_CHECKING:
    from types import ModuleType

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_forward_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Set up Spook ectoplasms."""
    LOGGER.debug("Setting up Spook ectoplasms")

    modules: list[ModuleType] = []

    def _load_all_ectoplasm_modules() -> None:
        """Load all Spook ectoplasm modules."""
        for module_file in Path(__file__).parent.rglob("ectoplasms/*/__init__.py"):
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace(
                "/",
                ".",
            )
            LOGGER.debug("Loading Spook ectoplasm: %s", module_path)
            module = importlib.import_module(f".{module_path}", __package__)
            if hasattr(module, "async_setup_entry"):
                modules.append(module)
                LOGGER.debug("Setting up Spook ectoplasm: %s", module_path)

    await hass.async_add_import_executor_job(_load_all_ectoplasm_modules)
    await asyncio.gather(
        *(_async_setup_ectoplasm(hass, entry, module) for module in modules)
    )


async def _async_setup_ectoplasm(
    hass: HomeAssistant,
    entry: ConfigEntry,
    module: ModuleType,
) -> None:
    """Set up a single ectoplasm, isolating failures.

    An ectoplasm that fails to set up must not prevent the rest of Spook
    from loading.
    """
    try:
        await module.async_setup_entry(hass, entry)
    # pylint: disable-next=broad-exception-caught
    except Exception:  # noqa: BLE001
        LOGGER.exception(
            "Spook ectoplasm %s failed to set up and has been skipped; "
            "please report this issue at https://github.com/frenck/spook/issues",
            module.__name__,
        )


async def async_forward_platform_entry_setups_to_ectoplasm(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: Platform,
) -> None:
    """Set up Spook ectoplasm platform."""
    LOGGER.debug("Setting up Spook ectoplasm platform: %s", platform)

    modules: list[ModuleType] = []

    def _load_all_ectoplasm_platform_modules() -> None:
        """Load all Spook ectoplasm platform modules."""
        for module_file in Path(__file__).parent.rglob(f"ectoplasms/*/{platform}.py"):
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace(
                "/",
                ".",
            )
            LOGGER.debug("Loading Spook %s from ectoplasm: %s", platform, module_path)
            modules.append(importlib.import_module(f".{module_path}", __package__))
            LOGGER.debug("Setting up Spook ectoplasm %s: %s", platform, module_path)

    await hass.async_add_import_executor_job(_load_all_ectoplasm_platform_modules)
    await asyncio.gather(
        *(
            _async_setup_ectoplasm_platform(hass, entry, async_add_entities, module)
            for module in modules
        )
    )


async def _async_setup_ectoplasm_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    module: ModuleType,
) -> None:
    """Set up a single ectoplasm platform, isolating failures.

    An ectoplasm platform that fails to set up must not prevent the rest
    of Spook from loading.
    """
    try:
        await module.async_setup_entry(hass, entry, async_add_entities)
    # pylint: disable-next=broad-exception-caught
    except Exception:  # noqa: BLE001
        LOGGER.exception(
            "Spook ectoplasm platform %s failed to set up and has been skipped; "
            "please report this issue at https://github.com/frenck/spook/issues",
            module.__name__,
        )
