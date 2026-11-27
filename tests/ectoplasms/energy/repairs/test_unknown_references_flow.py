"""Tests for taking unknown entities out of the energy settings from the repair."""

# The flow's steps are what there is to drive, and its data is private.
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.energy import const as energy_const
from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.energy.validate import ValidationIssues

from custom_components.spook import energy_preferences, repairs
from custom_components.spook.energy_preferences import async_unknown_energy_entities
from custom_components.spook.repairs import (
    EnergyUnknownReferencesFixFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from homeassistant.components.energy.data import EnergyManager
    from homeassistant.core import HomeAssistant

_ISSUE_ID = "energy_unknown_references_energy_unknown_references"

_PREFERENCES: dict[str, Any] = {
    "energy_sources": [
        {"type": "solar", "stat_energy_from": "sensor.gone_solar"},
        {
            "type": "gas",
            "stat_energy_from": "sensor.gas",
            "stat_cost": None,
            "entity_energy_price": "sensor.gone_price",
            "number_energy_price": None,
        },
    ],
    "device_consumption": [{"stat_consumption": "sensor.fridge"}],
    "device_consumption_water": [],
}


async def _energy_settings(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    unknown: set[str],
) -> Any:
    """Give Home Assistant these energy settings, with these entities unknown."""
    manager = await async_get_manager(hass)
    manager.data = {key: list(value) for key, value in _PREFERENCES.items()}

    async def _async_unknown(_hass: HomeAssistant) -> set[str]:
        return set(unknown)

    monkeypatch.setattr(repairs, "async_unknown_energy_entities", _async_unknown)
    return manager


def _flow(hass: HomeAssistant, offered: str) -> EnergyUnknownReferencesFixFlow:
    """Return the fix flow for an issue that showed these entities."""
    flow = EnergyUnknownReferencesFixFlow()
    flow.hass = hass
    # Through the context, the way the flow manager hands it over: Home
    # Assistant 2026.12 turns away a flow that has it set directly.
    flow.context = {"issue_id": _ISSUE_ID}
    flow.data = {"energy_unknown_entity_ids": offered, "entities": "- the list"}
    return flow


async def test_the_flow_is_chosen_for_this_issue(hass: HomeAssistant) -> None:
    """Test the energy issue gets the menu with the three choices."""
    flow = await async_create_fix_flow(
        hass, _ISSUE_ID, {"energy_unknown_entity_ids": "sensor.gone_solar"}
    )

    assert isinstance(flow, EnergyUnknownReferencesFixFlow)


async def test_the_menu_lists_what_was_shown(hass: HomeAssistant) -> None:
    """Test the menu names the entities the way the issue named them."""
    result = await _flow(hass, "sensor.gone_solar").async_step_init()

    assert result["menu_options"] == ["remove", "manage", "ignore"]
    assert result["description_placeholders"] == {"entities": "- the list"}


async def test_taking_out_cleans_the_settings(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the meter takes its source along, and the price is only cleared."""
    manager = await _energy_settings(
        hass, monkeypatch, {"sensor.gone_solar", "sensor.gone_price"}
    )

    result = await _flow(
        hass, "sensor.gone_solar,sensor.gone_price"
    ).async_step_remove()

    assert result["type"] == "create_entry"
    assert manager.data["energy_sources"] == [
        {
            "type": "gas",
            "stat_energy_from": "sensor.gas",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": None,
        }
    ]
    assert manager.data["device_consumption"] == [{"stat_consumption": "sensor.fridge"}]


async def test_one_that_came_back_is_left_alone(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an entity known again when the button is pressed stays."""
    manager = await _energy_settings(hass, monkeypatch, {"sensor.gone_price"})

    await _flow(hass, "sensor.gone_solar,sensor.gone_price").async_step_remove()

    assert manager.data["energy_sources"][0] == {
        "type": "solar",
        "stat_energy_from": "sensor.gone_solar",
    }


async def test_nothing_is_taken_out_that_was_never_shown(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an entity that went missing after the issue was raised stays."""
    manager = await _energy_settings(
        hass, monkeypatch, {"sensor.gone_solar", "sensor.gone_price"}
    )

    await _flow(hass, "sensor.gone_solar").async_step_remove()

    assert manager.data["energy_sources"][0]["entity_energy_price"] == (
        "sensor.gone_price"
    )


async def test_everything_back_takes_out_nothing(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the flow says so when nothing it showed is still unknown."""
    manager = await _energy_settings(hass, monkeypatch, set())

    result = await _flow(hass, "sensor.gone_solar").async_step_remove()

    assert result["type"] == "abort"
    assert result["reason"] == "nothing_to_remove"
    assert manager.data["energy_sources"] == _PREFERENCES["energy_sources"]


async def test_settings_changed_elsewhere_take_out_nothing(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an entity somebody took out already leaves nothing to write."""
    manager = await _energy_settings(hass, monkeypatch, {"sensor.elsewhere"})

    result = await _flow(hass, "sensor.elsewhere").async_step_remove()

    assert result["type"] == "abort"
    assert result["reason"] == "nothing_to_remove"
    assert manager.data["energy_sources"] == _PREFERENCES["energy_sources"]


GONE = "sensor.gone"

# A battery measured per direction, in the shape of Home Assistant 2026.12
# (`BatterySourceType` in its energy data): a meter for each way the energy
# goes, seen from the battery.
_BATTERY_PER_DIRECTION: dict[str, Any] = {
    "type": "battery",
    "stat_energy_from_grid": "sensor.charged_from_grid",
    "stat_energy_from_solar": "sensor.charged_from_solar",
    "stat_energy_to_home": "sensor.discharged_to_home",
    "stat_energy_to_grid": "sensor.discharged_to_grid",
}


def _settings_of_2026_12(**settings: Any) -> dict[str, Any]:
    """Return energy settings in the shape of Home Assistant 2026.12.

    That is `EnergyPreferences` in its energy data, which has gas devices.
    """
    return {
        "energy_sources": [],
        "device_consumption": [],
        "device_consumption_water": [],
        "device_consumption_gas": [],
        **settings,
    }


def _battery(**changes: Any) -> dict[str, Any]:
    """Return energy settings holding the battery, with these settings changed."""
    return _settings_of_2026_12(energy_sources=[{**_BATTERY_PER_DIRECTION, **changes}])


def _install_validation_of_2026_12(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    manager: EnergyManager,
) -> None:
    """Make Home Assistant report GONE wherever the energy settings name it.

    Grouped the way Home Assistant 2026.12 groups it: one result per source
    and per device, with the gas devices in a group of their own that older
    versions do not have. It reports every meter and power sensor of a
    battery measured per direction, and the meter of every gas device.
    """

    def _issues(setting: dict[str, Any]) -> ValidationIssues:
        issues = ValidationIssues()
        if GONE in json.dumps(setting):
            issues.add_issue(hass, "entity_not_defined", GONE)
        return issues

    async def _async_validate(_hass: HomeAssistant) -> SimpleNamespace:
        return SimpleNamespace(
            **{
                group: [_issues(setting) for setting in manager.data.get(group, [])]
                for group in _settings_of_2026_12()
            }
        )

    monkeypatch.setattr(energy_preferences, "async_validate", _async_validate)


# Home Assistant takes gas devices into its energy settings from 2026.12,
# and an older one drops them from an update. So that one only runs on a
# Home Assistant that has them, like the daily run against its development
# branch.
_GAS_DEVICES_TAKEN = pytest.mark.skipif(
    not hasattr(energy_const, "BATTERY_DIRECTIONS"),
    reason="needs the energy settings of Home Assistant 2026.12 or later",
)


@pytest.mark.parametrize(
    "preferences",
    [
        _battery(stat_energy_from_grid=GONE),
        _battery(stat_energy_from_solar=GONE),
        _battery(stat_energy_to_home=GONE),
        _battery(stat_energy_to_grid=GONE),
        _battery(power_config={"stat_rate_from_grid": GONE}),
        _battery(power_config={"stat_rate_from_solar": GONE}),
        _battery(power_config={"stat_rate_to_home": GONE}),
        _battery(power_config={"stat_rate_to_grid": GONE}),
        pytest.param(
            _settings_of_2026_12(device_consumption_gas=[{"stat_consumption": GONE}]),
            marks=_GAS_DEVICES_TAKEN,
        ),
    ],
    ids=[
        "battery meter from grid",
        "battery meter from solar",
        "battery meter to home",
        "battery meter to grid",
        "battery power from grid",
        "battery power from solar",
        "battery power to home",
        "battery power to grid",
        "gas device",
    ],
)
async def test_what_was_taken_out_is_not_found_again(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    preferences: dict[str, Any],
) -> None:
    """Test a look after the button finds nothing left of what it took out.

    A fix that leaves the entity somewhere in the settings leaves the issue
    standing, and pressing the button again does the same thing again.
    """
    manager = await async_get_manager(hass)
    manager.data = copy.deepcopy(preferences)
    _install_validation_of_2026_12(hass, monkeypatch, manager)

    assert await async_unknown_energy_entities(hass) == {GONE}

    result = await _flow(hass, GONE).async_step_remove()

    assert result["type"] == "create_entry"
    assert await async_unknown_energy_entities(hass) == set()
