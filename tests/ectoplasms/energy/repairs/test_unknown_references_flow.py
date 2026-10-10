"""Tests for taking unknown entities out of the energy settings from the repair."""

# The flow's steps are what there is to drive, and its data is private.
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.energy.data import async_get_manager

from custom_components.spook import repairs
from custom_components.spook.repairs import (
    EnergyUnknownReferencesFixFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    import pytest

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
    flow.issue_id = _ISSUE_ID
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
