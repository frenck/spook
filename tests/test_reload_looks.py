"""Tests for which reloads send a repair in for another look."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.components.automation import EVENT_AUTOMATION_RELOADED
from homeassistant.const import EVENT_CALL_SERVICE, EVENT_STATE_CHANGED
from homeassistant.core import State
from homeassistant.setup import async_setup_component

import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.spook.repairs import AbstractSpookRepair

# Repairs that hear about every change they care about where it happens, so
# a reload of some other domain is no reason for them to look, and neither
# is the call of their own: they hear when that one is done.
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
    "script.repairs.never_true_templates",
    "script.repairs.unknown_area_references",
    "script.repairs.unknown_condition_references",
    "script.repairs.unknown_config_entry_references",
    "script.repairs.unknown_device_references",
    "script.repairs.unknown_floor_references",
    "script.repairs.unknown_icons",
    "script.repairs.unknown_label_references",
    "script.repairs.unknown_service_references",
    "script.repairs.unknown_trigger_references",
    "script.repairs.unknown_user_references",
]

_AUTOMATION_REPAIRS = [
    name for name in _NOT_WOKEN_BY_OTHER_RELOADS if name.startswith("automation.")
]
_SCRIPT_REPAIRS = [
    name for name in _NOT_WOKEN_BY_OTHER_RELOADS if name.startswith("script.")
]

# Every script repair that looks again when a script comes or goes, the
# ones about attributes and states included.
_LOOKING_WHEN_SCRIPTS_COME_OR_GO = [
    *_SCRIPT_REPAIRS,
    "script.repairs.unknown_attribute_references",
    "script.repairs.unknown_state_references",
]


def _repair_class(module: str) -> type[AbstractSpookRepair]:
    """Return the repair a module of the ectoplasms holds."""
    return import_module(f"custom_components.spook.ectoplasms.{module}").SpookRepair


def _counted_looks(repair: AbstractSpookRepair) -> list[None]:
    """Swap an activated repair's debouncer for a list of the looks asked for."""
    repair.inspect_debouncer.async_shutdown()
    looks: list[None] = []

    async def _async_asked() -> None:
        looks.append(None)

    repair.inspect_debouncer = SimpleNamespace(
        async_call=_async_asked,
        async_schedule_call=lambda: looks.append(None),
        async_shutdown=lambda: None,
    )
    return looks


async def _count_looks_asked_for(
    hass: HomeAssistant, repair: AbstractSpookRepair, event_type: str, data: dict
) -> int:
    """Return how many looks one event asks an activated repair for."""
    looks = _counted_looks(repair)

    hass.bus.async_fire(event_type, data)
    await hass.async_block_till_done()
    return len(looks)


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
    registries, dashboards, their own reload event, or their own entities
    coming back once their reload is done.
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


_ADDED = {"old_state": None, "new_state": State("script.wake_up", "off")}
_REMOVED = {"old_state": State("script.wake_up", "off"), "new_state": None}
_RAN = {
    "old_state": State("script.wake_up", "off"),
    "new_state": State("script.wake_up", "on"),
}


@pytest.mark.parametrize("module", _SCRIPT_REPAIRS)
@pytest.mark.parametrize(
    ("change", "expected_looks"),
    [
        ({"entity_id": "script.wake_up", **_ADDED}, 1),
        ({"entity_id": "script.wake_up", **_REMOVED}, 1),
        ({"entity_id": "script.wake_up", **_RAN}, 0),
        ({"entity_id": "light.kitchen", **_ADDED}, 0),
    ],
    ids=["script added", "script removed", "script ran", "other entity added"],
)
async def test_script_repairs_look_once_their_reload_is_done(
    hass: HomeAssistant, module: str, change: dict, expected_looks: int
) -> None:
    """Test a script repair looks again when one of the scripts comes or goes.

    Scripts send no event when they reloaded. What a reload does: every
    script that changed is removed, and added back once it is done, so that
    is the look that sees the new configuration.
    """
    repair = _repair_class(module)(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(hass, repair, EVENT_STATE_CHANGED, change)
    await repair.async_deactivate()

    assert looks == expected_looks


def _scripts(sequence: list[Any]) -> dict[str, Any]:
    """Return a configuration holding one script."""
    return {"script": {"wake_up": {"sequence": sequence}}}


async def _looks_after_a_script_reload(
    hass: HomeAssistant, module: str, sequence: list[Any]
) -> int:
    """Return how many looks a real script reload asks a repair for."""
    assert await async_setup_component(hass, "script", _scripts([]))
    await hass.async_block_till_done()
    repair = _repair_class(module)(hass)
    await repair.async_activate()
    looks = _counted_looks(repair)

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=_scripts(sequence),
    ):
        await hass.services.async_call("script", "reload", blocking=True)
    await hass.async_block_till_done()
    await repair.async_deactivate()

    return len(looks)


@pytest.mark.parametrize("module", _LOOKING_WHEN_SCRIPTS_COME_OR_GO)
async def test_script_repairs_look_after_an_edited_script_reloads(
    hass: HomeAssistant, module: str
) -> None:
    """Test an edited script, really reloaded, gets a look.

    A script is in the entity registry, so a reload never takes its state
    away: it turns unavailable and restored until the script is back. That
    has to count as the script going and coming back, or no reload would.
    """
    assert await _looks_after_a_script_reload(hass, module, [{"delay": 1}])


@pytest.mark.parametrize("module", _SCRIPT_REPAIRS)
async def test_script_repairs_leave_a_reload_that_changed_nothing_alone(
    hass: HomeAssistant, module: str
) -> None:
    """Test a reload that left every script as it was asks for no look."""
    assert await _looks_after_a_script_reload(hass, module, []) == 0
