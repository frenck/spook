"""Spook - Your homie. Ectoplasm setup forwarding helpers."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.util.hass_dict import HassKey

from .const import LOGGER, PLATFORMS

if TYPE_CHECKING:
    from types import ModuleType

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

# The ectoplasm modules of every platform, imported before the platforms are
# forwarded. Or what went wrong importing them, for that platform to raise.
DATA_ECTOPLASM_PLATFORMS: HassKey[dict[Platform, list[ModuleType] | Exception]] = (
    HassKey("spook_ectoplasm_platforms")
)


def _import_ectoplasm_platform_modules(platform: Platform) -> list[ModuleType]:
    """Import the ectoplasm modules of one platform."""
    modules: list[ModuleType] = []
    for module_file in Path(__file__).parent.rglob(f"ectoplasms/*/{platform}.py"):
        module_path = str(module_file.relative_to(Path(__file__).parent))[:-3].replace(
            "/",
            ".",
        )
        LOGGER.debug("Loading Spook %s from ectoplasm: %s", platform, module_path)
        modules.append(importlib.import_module(f".{module_path}", __package__))
    return modules


async def async_forward_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Set up Spook ectoplasms."""
    LOGGER.debug("Setting up Spook ectoplasms")

    modules: list[ModuleType] = []
    platform_modules: dict[Platform, list[ModuleType] | Exception] = {}

    def _load_all_ectoplasm_modules() -> None:
        """Load all Spook ectoplasm modules, and those of every platform."""
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

        # The platforms used to import their own, each in a job of its own on
        # the import executor. That has one thread, every integration starting
        # up queues on it, and the wait counted against each platform's setup
        # timeout. #1898. Imported here, a platform has nothing to wait for.
        for platform in PLATFORMS:
            try:
                platform_modules[platform] = _import_ectoplasm_platform_modules(
                    platform
                )
            # Kept for the platform to raise. A module that does not import
            # fails only its own platform, as it did when it was imported there.
            # pylint: disable-next=broad-exception-caught
            except Exception as err:  # noqa: BLE001
                platform_modules[platform] = err

    await hass.async_add_import_executor_job(_load_all_ectoplasm_modules)

    hass.data[DATA_ECTOPLASM_PLATFORMS] = platform_modules

    @callback
    def _forget_platform_modules() -> None:
        """Leave nothing behind for a later setup to find."""
        hass.data.pop(DATA_ECTOPLASM_PLATFORMS, None)

    entry.async_on_unload(_forget_platform_modules)

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

    modules = hass.data[DATA_ECTOPLASM_PLATFORMS][platform]
    if isinstance(modules, Exception):
        raise modules

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
