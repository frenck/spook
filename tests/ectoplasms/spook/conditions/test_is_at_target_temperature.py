"""Tests for the spook.is_at_target_temperature condition."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.helpers.condition import ConditionConfig
from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from custom_components.spook.condition import async_get_conditions
from custom_components.spook.ectoplasms.spook.conditions.is_at_target_temperature import (
    SpookCondition,
)

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the condition platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

BATHROOM = "climate.bathroom"
KITCHEN = "climate.kitchen"


def _heating(current: float, target: float = 21.0) -> dict:
    """Return the attributes of a thermostat heating to one setpoint."""
    return {"current_temperature": current, "temperature": target}


async def _ask(
    hass: HomeAssistant,
    target: dict | None = None,
    **options: object,
) -> bool:
    """Validate, build and ask the condition once."""
    validated = await SpookCondition.async_validate_config(
        hass,
        {"target": target or {"entity_id": BATHROOM}, "options": options},
    )
    condition = SpookCondition(
        hass,
        ConditionConfig(target=validated["target"], options=validated["options"]),
    )
    await condition.async_setup()
    return bool(condition.async_check())


async def test_the_condition_is_discovered(hass: HomeAssistant) -> None:
    """The condition turns up in Spook's discovery, under a plain key."""
    conditions = await async_get_conditions(hass)

    assert conditions["is_at_target_temperature"] is SpookCondition


@pytest.mark.parametrize("target", [None, {}, {"entity_id": []}])
async def test_a_target_is_required(hass: HomeAssistant, target: object) -> None:
    """Without a thermostat, there is nothing to be at its target."""
    config = {} if target is None else {"target": target}
    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(hass, config)


@pytest.mark.parametrize(
    "options", [{"behavior": "most"}, {"tolerance": -1}, {"tolerance": "inf"}]
)
async def test_options_that_make_no_sense_are_refused(
    hass: HomeAssistant, options: dict
) -> None:
    """Any or all, and a tolerance of zero or more."""
    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(
            hass, {"target": {"entity_id": BATHROOM}, "options": options}
        )


@pytest.mark.parametrize(
    ("current", "expected"),
    [(21.0, True), (20.0, False), (22.0, False)],
    ids=["there", "below", "above"],
)
async def test_it_passes_at_the_target(
    hass: HomeAssistant, current: float, *, expected: bool
) -> None:
    """The point of the whole thing."""
    hass.states.async_set(BATHROOM, "heat", _heating(current))

    assert await _ask(hass) is expected


async def test_a_tolerance_counts_close_enough(hass: HomeAssistant) -> None:
    """A thermostat settling just short of its setpoint is there."""
    hass.states.async_set(BATHROOM, "heat", _heating(20.6))

    assert await _ask(hass) is False
    assert await _ask(hass, tolerance=0.5) is True


async def test_a_band_is_there_anywhere_inside_it(hass: HomeAssistant) -> None:
    """Heating and cooling to a range is there anywhere in the range."""
    hass.states.async_set(
        BATHROOM,
        "heat_cool",
        {
            "current_temperature": 23.0,
            "temperature": 25.0,
            "target_temp_low": 20.0,
            "target_temp_high": 24.0,
        },
    )

    assert await _ask(hass) is True


async def test_a_device_that_is_off_is_not_there(hass: HomeAssistant) -> None:
    """A heater that is off is working towards nothing."""
    hass.states.async_set(BATHROOM, STATE_OFF, _heating(21.0))

    assert await _ask(hass) is False


@pytest.mark.parametrize(("behavior", "expected"), [("any", True), ("all", False)])
async def test_any_or_all(
    hass: HomeAssistant, behavior: str, *, expected: bool
) -> None:
    """One warm room is enough for any, not for all."""
    hass.states.async_set(BATHROOM, "heat", _heating(21.0))
    hass.states.async_set(KITCHEN, "heat", _heating(18.0))

    target = {"entity_id": [BATHROOM, KITCHEN]}
    assert await _ask(hass, target, behavior=behavior) is expected


async def test_an_unavailable_device_is_left_out(hass: HomeAssistant) -> None:
    """A device that is not answering is neither a yes nor a no."""
    hass.states.async_set(BATHROOM, "heat", _heating(21.0))
    hass.states.async_set(KITCHEN, STATE_UNAVAILABLE)

    target = {"entity_id": [BATHROOM, KITCHEN]}
    assert await _ask(hass, target, behavior="all") is True


@pytest.mark.parametrize("behavior", ["any", "all"])
async def test_nothing_to_ask_is_not_a_yes(hass: HomeAssistant, behavior: str) -> None:
    """A bathroom whose thermostat is unavailable is not known to be warm.

    `all` of nothing would be true, which is exactly the wrong answer here.
    """
    hass.states.async_set(BATHROOM, STATE_UNAVAILABLE)

    assert await _ask(hass, behavior=behavior) is False


async def test_only_thermostats_and_water_heaters_in_an_area_count(
    hass: HomeAssistant,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """An area holds all sorts, whatever their attributes happen to be called."""
    area = area_registry.async_create("Bathroom")
    boiler = entity_registry.async_get_or_create("water_heater", "demo", "boiler")
    lookalike = entity_registry.async_get_or_create("sensor", "demo", "lookalike")
    for entry in (boiler, lookalike):
        entity_registry.async_update_entity(entry.entity_id, area_id=area.id)
    hass.states.async_set(boiler.entity_id, "eco", _heating(55.0, target=55.0))
    hass.states.async_set(lookalike.entity_id, "on", _heating(10.0))

    assert await _ask(hass, {"area_id": area.id}, behavior="all") is True


async def test_it_works_in_an_automation(hass: HomeAssistant) -> None:
    """Configured the way an automation does it, through the whole path."""
    hass.states.async_set(BATHROOM, "heat", _heating(21.0))
    ran: list[str] = []

    async def _mark(_call) -> None:  # noqa: ANN001
        ran.append("ran")

    hass.services.async_register("test", "mark", _mark)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {"platform": "event", "event_type": "check"},
                "condition": {
                    "condition": "spook.is_at_target_temperature",
                    "target": {"entity_id": BATHROOM},
                },
                "action": {"action": "test.mark"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire("check")
    await hass.async_block_till_done()
    hass.states.async_set(BATHROOM, "heat", _heating(18.0))
    hass.bus.async_fire("check")
    await hass.async_block_till_done()

    assert ran == ["ran"]
