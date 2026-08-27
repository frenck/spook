"""Spook - Your homie."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import Condition

# Core calls ``async_get_conditions`` repeatedly (once per config validation
# and per condition instantiation), so the discovery result is cached rather
# than re-globbing and re-importing on every call.
DATA_CONDITIONS: HassKey[dict[str, type[Condition]]] = HassKey("spook_conditions")


async def async_get_conditions(
    hass: HomeAssistant,
) -> dict[str, type[Condition]]:
    """Return the conditions Spook provides.

    Discovered from the leaf modules under ``ectoplasms/*/conditions/``,
    each exposing a ``SpookCondition`` class; keys become ``spook.<key>``.
    """
    if (cached := hass.data.get(DATA_CONDITIONS)) is not None:
        return cached

    conditions: dict[str, type[Condition]] = {}

    def _load_all_condition_modules() -> None:
        """Load all condition modules and collect their conditions."""
        for module_file in Path(__file__).parent.rglob("ectoplasms/*/conditions/*.py"):
            if module_file.name == "__init__.py":
                continue
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace("/", ".")
            module = importlib.import_module(f".{module_path}", __package__)
            conditions[module.SpookCondition.condition] = module.SpookCondition

    await hass.async_add_import_executor_job(_load_all_condition_modules)
    hass.data[DATA_CONDITIONS] = conditions
    return conditions
