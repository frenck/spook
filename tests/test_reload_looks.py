"""Tests for which reloads send a repair in for another look."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.components.automation import EVENT_AUTOMATION_RELOADED
from homeassistant.const import EVENT_CALL_SERVICE

import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.spook.repairs import AbstractSpookRepair

# Repairs that hear about every change they care about where it happens, so
# a reload of some other domain is no reason for them to look.
_NOT_WOKEN_BY_OTHER_RELOADS = [
    "alert.repairs.unknown_entity_references",
    "alert.repairs.unknown_notifiers",
    "automation.repairs.never_true_templates",
    "automation.repairs.unknown_area_references",
    "automation.repairs.unknown_condition_references",
    "automation.repairs.unknown_config_entry_references",
    "automation.repairs.unknown_device_references",
    "automation.repairs.unknown_icons",
    "automation.repairs.unknown_service_references",
    "automation.repairs.unknown_trigger_id_references",
    "automation.repairs.unknown_trigger_references",
    "automation.repairs.unknown_user_references",
    "lovelace.repairs.unknown_area_references",
    "lovelace.repairs.unknown_icons",
    "lovelace.repairs.unknown_service_references",
    "lovelace.repairs.unknown_theme_references",
    "lovelace.repairs.unknown_user_references",
    "lovelace.repairs.unknown_view_references",
    "notify.repairs.unknown_group_members",
]

_AUTOMATION_REPAIRS = [
    name for name in _NOT_WOKEN_BY_OTHER_RELOADS if name.startswith("automation.")
]


def _repair_class(module: str) -> type[AbstractSpookRepair]:
    """Return the repair a module of the ectoplasms holds."""
    return import_module(f"custom_components.spook.ectoplasms.{module}").SpookRepair


async def _count_looks_asked_for(
    hass: HomeAssistant, repair: AbstractSpookRepair, event_type: str, data: dict
) -> int:
    """Return how many looks one event asks an activated repair for."""
    repair.inspect_debouncer.async_shutdown()
    looks = 0

    def _asked() -> None:
        nonlocal looks
        looks += 1

    async def _async_asked() -> None:
        _asked()

    repair.inspect_debouncer = SimpleNamespace(
        async_call=_async_asked,
        async_schedule_call=_asked,
        async_shutdown=lambda: None,
    )

    hass.bus.async_fire(event_type, data)
    await hass.async_block_till_done()
    return looks


@pytest.fixture(name="dashboards", autouse=True)
def dashboards_fixture(hass: HomeAssistant) -> None:
    """Give the dashboard repairs a Lovelace without dashboards to read."""
    hass.data["lovelace"] = SimpleNamespace(dashboards={})


@pytest.mark.parametrize("module", _NOT_WOKEN_BY_OTHER_RELOADS)
@pytest.mark.parametrize("domain", ["template", "group", "script", "input_select"])
async def test_a_reload_elsewhere_is_no_reason_to_look(
    hass: HomeAssistant, module: str, domain: str
) -> None:
    """Test a reload of another domain leaves these repairs alone.

    Every one of them used to look again after every reload of any domain,
    45 rounds for a single `template.reload`, for changes they already hear
    about where those happen: entities and actions coming and going,
    registries, dashboards, or their own reload event.
    """
    repair = _repair_class(module)(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(
        hass,
        repair,
        EVENT_CALL_SERVICE,
        {"domain": domain, "service": "reload", "service_data": {}},
    )
    await repair.async_deactivate()

    assert looks == 0


@pytest.mark.parametrize("module", _AUTOMATION_REPAIRS)
async def test_automation_repairs_look_once_their_reload_is_done(
    hass: HomeAssistant, module: str
) -> None:
    """Test an automation repair looks again once the automations reloaded.

    That is the look that sees the new configuration. The one the reload
    call used to start came three seconds after the call, finished or not.
    """
    repair = _repair_class(module)(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(hass, repair, EVENT_AUTOMATION_RELOADED, {})
    await repair.async_deactivate()

    assert looks == 1
