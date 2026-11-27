"""Tests for taking unknown entities out of the energy settings.

Home Assistant writes whatever it is given into the energy settings, so a
shape it cannot draw breaks the energy dashboard. Each setting is taken out
the way that setting allows, and that is what these pin down.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from homeassistant.components.energy import const as energy_const
from homeassistant.components.energy.data import (
    DEVICE_CONSUMPTION_SCHEMA,
    ENERGY_SOURCE_SCHEMA,
)

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


def test_gas_devices_are_cleaned_too() -> None:
    """Test the gas devices get the same as the energy ones.

    In the shape of Home Assistant 2026.12, the first to have them.
    """
    preferences = {
        "device_consumption_gas": [
            {"stat_consumption": GONE},
            {"stat_consumption": "sensor.stove", "included_in_stat": GONE},
        ]
    }

    assert energy_preferences_without(preferences, {GONE}) == {
        "device_consumption_gas": [{"stat_consumption": "sensor.stove"}]
    }


def test_a_capacity_sensor_is_left_out() -> None:
    """Test a battery stays when only the sensor for its capacity is unknown.

    In the shape of Home Assistant 2026.12, the first to have it.
    """
    preferences = _sources(
        {
            "type": "battery",
            "stat_energy_from": "sensor.out",
            "stat_energy_to": "sensor.in",
            "entity_capacity": GONE,
        }
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources(
        {
            "type": "battery",
            "stat_energy_from": "sensor.out",
            "stat_energy_to": "sensor.in",
        }
    )


# A battery measured per direction, in the shape of Home Assistant 2026.12
# (`BatterySourceType` and `PowerConfig` in its energy data): a meter for each
# way the energy goes, and a power sensor for each of those ways.
_PER_DIRECTION: dict[str, Any] = {
    "type": "battery",
    "stat_energy_from_grid": "sensor.charged_from_grid",
    "stat_energy_from_solar": "sensor.charged_from_solar",
    "stat_energy_to_home": "sensor.discharged_to_home",
    "stat_energy_to_grid": "sensor.discharged_to_grid",
    "stat_rate": "sensor.battery_power_generated",
    "power_config": {
        "stat_rate_from_grid": "sensor.charging_from_grid",
        "stat_rate_from_solar": "sensor.charging_from_solar",
        "stat_rate_to_home": "sensor.discharging_to_home",
        "stat_rate_to_grid": "sensor.discharging_to_grid",
    },
}


def _per_direction(**changes: Any) -> dict[str, Any]:
    """Return the battery measured per direction, with these settings changed."""
    return {**copy.deepcopy(_PER_DIRECTION), **changes}


def test_a_battery_per_direction_loses_only_the_way_that_is_gone() -> None:
    """Test a way's meter takes its power sensor along, and nothing else.

    Home Assistant turns away a power sensor for a way that has no meter.
    """
    preferences = _sources(_per_direction(stat_energy_from_grid=GONE))

    assert energy_preferences_without(preferences, {GONE}) == _sources(
        {
            "type": "battery",
            "stat_energy_from_solar": "sensor.charged_from_solar",
            "stat_energy_to_home": "sensor.discharged_to_home",
            "stat_energy_to_grid": "sensor.discharged_to_grid",
            "stat_rate": "sensor.battery_power_generated",
            "power_config": {
                "stat_rate_from_solar": "sensor.charging_from_solar",
                "stat_rate_to_home": "sensor.discharging_to_home",
                "stat_rate_to_grid": "sensor.discharging_to_grid",
            },
        }
    )


def test_a_power_sensor_for_one_way_is_left_out_alone() -> None:
    """Test the power sensors of the other ways stay, and so does the meter."""
    preferences = _sources(
        _per_direction(
            power_config={
                **_PER_DIRECTION["power_config"],
                "stat_rate_to_grid": GONE,
            }
        )
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources(
        _per_direction(
            power_config={
                "stat_rate_from_grid": "sensor.charging_from_grid",
                "stat_rate_from_solar": "sensor.charging_from_solar",
                "stat_rate_to_home": "sensor.discharging_to_home",
            }
        )
    )


def test_the_last_power_sensor_takes_the_rate_along() -> None:
    """Test a battery with no power sensor left has no power setting left.

    Home Assistant works the rate out of the power sensors, and turns away
    a battery measured per direction with a rate but no power config.
    """
    preferences = _sources(
        {
            "type": "battery",
            "stat_energy_from_grid": "sensor.charged_from_grid",
            "stat_energy_to_home": "sensor.discharged_to_home",
            "stat_rate": "sensor.battery_power_generated",
            "power_config": {"stat_rate_to_home": GONE},
        }
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources(
        {
            "type": "battery",
            "stat_energy_from_grid": "sensor.charged_from_grid",
            "stat_energy_to_home": "sensor.discharged_to_home",
        }
    )


@pytest.mark.parametrize(
    "gone_way",
    ["stat_energy_from_grid", "stat_energy_to_home"],
)
def test_a_battery_per_direction_without_a_way_in_or_out_goes(gone_way: str) -> None:
    """Test a battery left without a way in, or a way out, is dropped.

    The same as a battery measured in total that lost either of its meters:
    Home Assistant needs one charging and one discharging way at least.
    """
    preferences = _sources(
        {
            "type": "battery",
            "stat_energy_from_grid": "sensor.charged_from_grid",
            "stat_energy_to_home": "sensor.discharged_to_home",
            gone_way: GONE,
        }
    )

    assert energy_preferences_without(preferences, {GONE}) == _sources()


# What the cleaning leaves of energy settings in the shape of Home Assistant
# 2026.12 has to be settings that Home Assistant takes. Checked with the
# schemas the energy panel's save command checks with. For a battery measured
# per direction, those only exist from 2026.12, so those checks only run on a
# Home Assistant that has them, like the daily run against its development
# branch.
_SHAPE_OF_2026_12 = pytest.mark.skipif(
    not hasattr(energy_const, "BATTERY_DIRECTIONS"),
    reason="needs the energy settings of Home Assistant 2026.12 or later",
)


@_SHAPE_OF_2026_12
@pytest.mark.parametrize(
    "battery",
    [
        _per_direction(stat_energy_from_grid=GONE),
        _per_direction(stat_energy_to_home=GONE),
        _per_direction(
            power_config={**_PER_DIRECTION["power_config"], "stat_rate_to_grid": GONE}
        ),
        _per_direction(power_config={"stat_rate_from_grid": GONE}),
        _per_direction(entity_capacity=GONE),
    ],
)
def test_what_is_left_of_a_battery_is_taken_by_home_assistant(
    battery: dict[str, Any],
) -> None:
    """Test a battery that lost a meter or a sensor still validates."""
    cleaned = energy_preferences_without(_sources(battery), {GONE})

    assert ENERGY_SOURCE_SCHEMA(cleaned["energy_sources"])


def test_what_is_left_of_the_gas_devices_is_taken_by_home_assistant() -> None:
    """Test gas devices that lost a device, or a part of one, still validate."""
    preferences = {
        "device_consumption_gas": [
            {"stat_consumption": GONE},
            {"stat_consumption": "sensor.stove", "included_in_stat": GONE},
        ]
    }

    cleaned = energy_preferences_without(preferences, {GONE})

    assert [
        DEVICE_CONSUMPTION_SCHEMA(device)
        for device in cleaned["device_consumption_gas"]
    ]
