"""Tests for taking unknown entities out of the energy settings.

Home Assistant writes whatever it is given into the energy settings, so a
shape it cannot draw breaks the energy dashboard. Each setting is taken out
the way that setting allows, and that is what these pin down.
"""

from __future__ import annotations

import copy
from typing import Any

from custom_components.spook.energy_preferences import energy_preferences_without

GONE = "sensor.gone"


def _sources(*sources: dict[str, Any]) -> dict[str, Any]:
    """Return energy settings holding these sources."""
    return {"energy_sources": list(sources)}


def test_nothing_unknown_changes_nothing() -> None:
    """Test settings without the entity come back as they were."""
    preferences = {
        "energy_sources": [
            {"type": "solar", "stat_energy_from": "sensor.solar"},
        ],
        "device_consumption": [{"stat_consumption": "sensor.fridge"}],
    }

    assert energy_preferences_without(preferences, {GONE}) == preferences


def test_the_settings_passed_in_are_left_alone() -> None:
    """Test the settings Home Assistant holds are not changed underneath it."""
    preferences = _sources(
        {"type": "gas", "stat_energy_from": "sensor.gas", "stat_cost": GONE}
    )
    original = copy.deepcopy(preferences)

    energy_preferences_without(preferences, {GONE})

    assert preferences == original


def test_only_the_parts_the_settings_have_come_back() -> None:
    """Test a part the settings do not have is not made up as empty."""
    assert energy_preferences_without(_sources(), {GONE}) == {"energy_sources": []}


def test_a_source_without_its_meter_goes() -> None:
    """Test solar, gas and water go when their meter is unknown."""
    preferences = _sources(
        {"type": "solar", "stat_energy_from": GONE},
        {"type": "gas", "stat_energy_from": GONE, "stat_cost": None},
        {"type": "water", "stat_energy_from": "sensor.water"},
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources(
        {"type": "water", "stat_energy_from": "sensor.water"}
    )


def test_a_battery_missing_either_meter_goes() -> None:
    """Test a battery cannot do without what goes in, or what comes out."""
    preferences = _sources(
        {"type": "battery", "stat_energy_from": "sensor.out", "stat_energy_to": GONE},
        {"type": "battery", "stat_energy_from": GONE, "stat_energy_to": "sensor.in"},
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources()


def test_a_price_or_a_cost_is_only_cleared() -> None:
    """Test a meter stays when only its price or its cost is unknown."""
    preferences = _sources(
        {
            "type": "gas",
            "stat_energy_from": "sensor.gas",
            "stat_cost": None,
            "entity_energy_price": GONE,
            "number_energy_price": None,
        },
        {
            "type": "water",
            "stat_energy_from": "sensor.water",
            "stat_cost": GONE,
            "entity_energy_price": None,
            "number_energy_price": 2.5,
        },
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources(
        {
            "type": "gas",
            "stat_energy_from": "sensor.gas",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": None,
        },
        {
            "type": "water",
            "stat_energy_from": "sensor.water",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": 2.5,
        },
    )


def test_an_optional_extra_is_left_out() -> None:
    """Test power and the state of charge are dropped, the source stays."""
    preferences = _sources(
        {
            "type": "battery",
            "stat_energy_from": "sensor.out",
            "stat_energy_to": "sensor.in",
            "stat_rate": GONE,
            "stat_soc": GONE,
        }
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources(
        {
            "type": "battery",
            "stat_energy_from": "sensor.out",
            "stat_energy_to": "sensor.in",
        }
    )


def test_power_settings_go_together() -> None:
    """Test a power config leaning on something unknown takes its rate along.

    Home Assistant works the power sensor out of the config and writes it as
    the rate, so the one is not left without the other.
    """
    preferences = _sources(
        {
            "type": "battery",
            "stat_energy_from": "sensor.out",
            "stat_energy_to": "sensor.in",
            "stat_rate": "sensor.battery_power_generated",
            "power_config": {"stat_rate_from": GONE, "stat_rate_to": "sensor.to"},
        }
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources(
        {
            "type": "battery",
            "stat_energy_from": "sensor.out",
            "stat_energy_to": "sensor.in",
        }
    )


def test_a_grid_connection_loses_only_the_way_that_is_gone() -> None:
    """Test a grid connection keeps exporting when its import meter is gone."""
    preferences = _sources(
        {
            "type": "grid",
            "stat_energy_from": GONE,
            "stat_cost": "sensor.cost",
            "entity_energy_price": "sensor.price",
            "number_energy_price": None,
            "stat_energy_to": "sensor.exported",
            "stat_compensation": None,
            "entity_energy_price_export": None,
            "number_energy_price_export": 0.08,
            "cost_adjustment_day": 0.0,
        }
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources(
        {
            "type": "grid",
            "stat_energy_from": None,
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": None,
            "stat_energy_to": "sensor.exported",
            "stat_compensation": None,
            "entity_energy_price_export": None,
            "number_energy_price_export": 0.08,
            "cost_adjustment_day": 0.0,
        }
    )


def test_a_grid_connection_with_nothing_left_goes() -> None:
    """Test a grid connection without import, export or power is dropped."""
    preferences = _sources(
        {
            "type": "grid",
            "stat_energy_from": GONE,
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": 0.3,
            "stat_energy_to": None,
            "stat_compensation": None,
            "entity_energy_price_export": None,
            "number_energy_price_export": None,
            "cost_adjustment_day": 0.0,
        }
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources()


def test_a_grid_connection_with_power_left_stays() -> None:
    """Test a grid connection measuring power only is still a connection."""
    preferences = _sources(
        {
            "type": "grid",
            "stat_energy_from": GONE,
            "stat_energy_to": None,
            "stat_rate": "sensor.grid_power",
            "cost_adjustment_day": 0.0,
        }
    )

    cleaned = energy_preferences_without(preferences, {GONE})

    assert cleaned["energy_sources"][0]["stat_rate"] == "sensor.grid_power"


def test_an_export_price_on_the_grid_is_only_cleared() -> None:
    """Test the grid keeps exporting when only its export price is gone."""
    preferences = _sources(
        {
            "type": "grid",
            "stat_energy_from": "sensor.imported",
            "stat_energy_to": "sensor.exported",
            "entity_energy_price_export": GONE,
            "cost_adjustment_day": 0.0,
        }
    )

    cleaned = energy_preferences_without(preferences, {GONE})["energy_sources"][0]

    assert cleaned["entity_energy_price_export"] is None
    assert cleaned["stat_energy_to"] == "sensor.exported"


def test_the_older_grid_form_loses_only_the_flow_that_is_gone() -> None:
    """Test a grid connection in the older form keeps its other flows.

    Home Assistant up to 2026.9 keeps the grid in flows, and Spook runs on
    those versions too.
    """
    preferences = _sources(
        {
            "type": "grid",
            "flow_from": [
                {"stat_energy_from": GONE, "stat_cost": None},
                {"stat_energy_from": "sensor.night", "entity_energy_price": GONE},
            ],
            "flow_to": [
                {"stat_energy_to": "sensor.exported", "stat_compensation": None}
            ],
            "cost_adjustment_day": 0.0,
        }
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources(
        {
            "type": "grid",
            "flow_from": [
                {"stat_energy_from": "sensor.night", "entity_energy_price": None},
            ],
            "flow_to": [
                {"stat_energy_to": "sensor.exported", "stat_compensation": None}
            ],
            "cost_adjustment_day": 0.0,
        }
    )


def test_the_older_grid_form_with_nothing_left_goes() -> None:
    """Test an older grid connection without a flow or power left is dropped."""
    preferences = _sources(
        {
            "type": "grid",
            "flow_from": [{"stat_energy_from": GONE}],
            "flow_to": [],
            "power": [{"stat_rate": GONE}],
            "cost_adjustment_day": 0.0,
        }
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources()


def test_a_device_without_its_meter_goes_and_takes_its_parts_along() -> None:
    """Test a device that was part of a dropped device stops saying so.

    Left pointing at it, the energy dashboard would draw it as part of a
    device that is not there.
    """
    preferences = {
        "device_consumption": [
            {"stat_consumption": GONE},
            {"stat_consumption": "sensor.fridge", "included_in_stat": GONE},
            {"stat_consumption": "sensor.oven", "stat_rate": GONE},
        ]
    }

    assert energy_preferences_without(preferences, {GONE}) == {
        "device_consumption": [
            {"stat_consumption": "sensor.fridge"},
            {"stat_consumption": "sensor.oven"},
        ]
    }


def test_water_devices_are_cleaned_too() -> None:
    """Test the water devices get the same as the energy ones."""
    preferences = {
        "device_consumption_water": [
            {"stat_consumption": GONE},
            {"stat_consumption": "sensor.shower"},
        ]
    }

    assert energy_preferences_without(preferences, {GONE}) == {
        "device_consumption_water": [{"stat_consumption": "sensor.shower"}]
    }
