"""Spook - Your homie."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.trigger import Trigger

# Core calls ``async_get_triggers`` repeatedly (once per config validation and
# per trigger instantiation), so the discovery result is cached rather than
# re-globbing and re-importing on every call.
DATA_TRIGGERS: HassKey[dict[str, type[Trigger]]] = HassKey("spook_triggers")


async def async_get_triggers(
    hass: HomeAssistant,
) -> dict[str, type[Trigger]]:
    """Return the triggers Spook provides.

    Discovered from the leaf modules under ``ectoplasms/*/triggers/``, each
    exposing a ``SpookTrigger`` class; keys become ``spook.<key>``.
    """
    if (cached := hass.data.get(DATA_TRIGGERS)) is not None:
        return cached

    triggers: dict[str, type[Trigger]] = {}

    def _load_all_trigger_modules() -> None:
        """Load all trigger modules and collect their triggers."""
        for module_file in Path(__file__).parent.rglob("ectoplasms/*/triggers/*.py"):
            if module_file.name == "__init__.py":
                continue
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace("/", ".")
            module = importlib.import_module(f".{module_path}", __package__)
            triggers[module.SpookTrigger.trigger] = module.SpookTrigger

    await hass.async_add_import_executor_job(_load_all_trigger_modules)
    hass.data[DATA_TRIGGERS] = triggers
    return triggers
