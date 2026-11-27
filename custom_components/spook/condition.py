"""Spook - Your homie."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

from .const import LOGGER

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
        """Load all condition modules and collect their conditions, isolating failures.

        Home Assistant asks for these while it validates automations, where
        it only expects an invalid configuration. A condition that fails to
        import, most likely because Home Assistant moved or renamed something
        it uses, would otherwise fail the validation of every automation.
        Skipping it leaves only the automations that use it invalid.
        """
        for module_file in Path(__file__).parent.rglob("ectoplasms/*/conditions/*.py"):
            if module_file.name == "__init__.py":
                continue
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace("/", ".")

            try:
                module = importlib.import_module(f".{module_path}", __package__)
            # pylint: disable-next=broad-exception-caught
            except Exception:  # noqa: BLE001
                LOGGER.exception(
                    "Spook condition %s.%s failed to load and has been skipped; "
                    "please report this issue at "
                    "https://github.com/frenck/spook/issues",
                    __package__,
                    module_path,
                )
                continue

            conditions[module.SpookCondition.condition] = module.SpookCondition

    await hass.async_add_import_executor_job(_load_all_condition_modules)
    hass.data[DATA_CONDITIONS] = conditions
    return conditions
