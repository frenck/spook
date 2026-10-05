"""Tests for the spook.target_temperature_reached trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import Context
from homeassistant.helpers.trigger import TriggerConfig
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.target_temperature_reached import (
    SpookTrigger,
)
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

BATHROOM = "climate.bathroom"


def _heating(current: float, target: float = 21.0) -> dict:
    """Return the attributes of a thermostat heating to one setpoint."""
    return {"current_temperature": current, "temperature": target}


def _band(current: float, low: float = 20.0, high: float = 24.0) -> dict:
    """Return the attributes of a thermostat keeping to a band."""
    return {
        "current_temperature": current,
        "temperature": None,
        "target_temp_low": low,
        "target_temp_high": high,
    }


async def _attach(
    hass: HomeAssistant, target: dict | None = None, tolerance: float | None = None
) -> tuple[list[tuple[dict, Context | None]], Callable[[], None]]:
    """Attach the trigger, and record everything it hands over."""
    config: dict = {"target": target or {"entity_id": BATHROOM}}
    if tolerance is not None:
        config["options"] = {"tolerance": tolerance}
    validated = await SpookTrigger.async_validate_config(hass, config)

    handed: list[tuple[dict, Context | None]] = []
    trigger = SpookTrigger(
        hass,
        TriggerConfig(
            key="target_temperature_reached",
            target=validated["target"],
            options=validated["options"],
        ),
    )

    def _run(payload, _description, context=None) -> None:  # noqa: ANN001
        handed.append((payload, context))

    unsub = await trigger.async_attach_runner(_run)
    return handed, unsub


async def _set(
    hass: HomeAssistant,
    attributes: dict,
    state: str = "heat",
    entity_id: str = BATHROOM,
    context: Context | None = None,
) -> None:
    """Write a state and let it be handled."""
    hass.states.async_set(entity_id, state, attributes, context=context)
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "target_temperature_reached" in await async_get_triggers(hass)


@pytest.mark.parametrize("target", [None, {}, {"entity_id": []}])
async def test_a_target_is_required(hass: HomeAssistant, target: object) -> None:
    """Without a thermostat to watch, there is nothing to reach."""
    config = {} if target is None else {"target": target}
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(hass, config)


@pytest.mark.parametrize("tolerance", [-0.5, "inf", "nan", "warm"])
async def test_a_tolerance_that_is_no_distance_is_refused(
    hass: HomeAssistant, tolerance: object
) -> None:
    """A tolerance is a distance from the target, so zero or more."""
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(
            hass,
            {"target": {"entity_id": BATHROOM}, "options": {"tolerance": tolerance}},
        )


async def test_the_tolerance_defaults_to_the_target_itself(
    hass: HomeAssistant,
) -> None:
    """Left out, close enough is exactly there."""
    validated = await SpookTrigger.async_validate_config(
        hass, {"target": {"entity_id": BATHROOM}}
    )

    assert validated["options"]["tolerance"] == 0


async def test_heating_up_to_the_target_fires(hass: HomeAssistant) -> None:
    """The point of the whole thing."""
    await _set(hass, _heating(19.0))
    handed, unsub = await _attach(hass)

    await _set(hass, _heating(20.0))
    assert handed == []

    await _set(hass, _heating(21.0))
    unsub()

    assert len(handed) == 1
    payload, _context = handed[0]
    assert payload["entity_id"] == BATHROOM
    assert payload["to_state"].attributes == _heating(21.0)


@pytest.mark.parametrize(
    ("before", "after"),
    [(20.0, 22.0), (23.0, 20.0), (25.0, 21.0)],
    ids=["jumping past while heating", "jumping past while cooling", "cooling"],
)
async def test_getting_there_from_either_side_fires(
    hass: HomeAssistant, before: float, after: float
) -> None:
    """Jumping past counts: a sensor in whole degrees never reports 21."""
    await _set(hass, _heating(before))
    handed, unsub = await _attach(hass)

    await _set(hass, _heating(after))
    unsub()

    assert len(handed) == 1


async def test_staying_at_the_target_fires_once(hass: HomeAssistant) -> None:
    """Hovering around the target is not reaching it over and over."""
    await _set(hass, _heating(20.0))
    handed, unsub = await _attach(hass)

    await _set(hass, _heating(21.0))
    await _set(hass, _heating(21.0, target=21.0) | {"hvac_action": "idle"})
    unsub()

    assert len(handed) == 1


async def test_leaving_and_getting_back_fires_again(hass: HomeAssistant) -> None:
    """A window opened and closed again is a new trip to the target."""
    await _set(hass, _heating(20.0))
    handed, unsub = await _attach(hass)

    await _set(hass, _heating(21.0))
    await _set(hass, _heating(18.0))
    await _set(hass, _heating(21.0))
    unsub()

    assert len(handed) == 2  # noqa: PLR2004


async def test_moving_the_target_onto_the_temperature_does_not_fire(
    hass: HomeAssistant,
) -> None:
    """Somebody changing the setpoint did not make the room get anywhere."""
    await _set(hass, _heating(19.0, target=22.0))
    handed, unsub = await _attach(hass)

    await _set(hass, _heating(19.0, target=19.0))
    unsub()

    assert handed == []


async def test_the_next_trip_counts_against_the_new_target(
    hass: HomeAssistant,
) -> None:
    """Once the setpoint moved, reaching the new one counts."""
    await _set(hass, _heating(19.0, target=21.0))
    handed, unsub = await _attach(hass)

    await _set(hass, _heating(19.0, target=23.0))
    await _set(hass, _heating(21.0, target=23.0))
    assert handed == []

    await _set(hass, _heating(23.0, target=23.0))
    unsub()

    assert len(handed) == 1


async def test_a_device_that_is_off_reaches_nothing(hass: HomeAssistant) -> None:
    """A room drifting onto the setpoint of a heater that is off is weather."""
    await _set(hass, _heating(19.0), state=STATE_OFF)
    handed, unsub = await _attach(hass)

    await _set(hass, _heating(21.0), state=STATE_OFF)
    # Switched on while the room is already there: nothing was reached either.
    await _set(hass, _heating(21.0))
    unsub()

    assert handed == []


async def test_coming_back_at_the_target_is_not_reaching_it(
    hass: HomeAssistant,
) -> None:
    """With no temperature before, there is no movement to judge."""
    await _set(hass, _heating(19.0))
    handed, unsub = await _attach(hass)

    await _set(hass, {}, state=STATE_UNAVAILABLE)
    await _set(hass, _heating(21.0))
    unsub()

    assert handed == []


async def test_a_tolerance_counts_close_enough(hass: HomeAssistant) -> None:
    """A thermostat settling just short of its setpoint got there."""
    await _set(hass, _heating(19.0))
    handed, unsub = await _attach(hass, tolerance=0.5)

    await _set(hass, _heating(20.4))
    assert handed == []

    await _set(hass, _heating(20.6))
    unsub()

    assert len(handed) == 1


@pytest.mark.parametrize(
    ("before", "after", "fires"),
    [(18.0, 21.0, True), (26.0, 23.0, True), (22.0, 23.0, False), (17.0, 19.0, False)],
    ids=["warming into it", "cooling into it", "inside already", "not there yet"],
)
async def test_a_band_is_reached_anywhere_inside_it(
    hass: HomeAssistant, before: float, after: float, *, fires: bool
) -> None:
    """Heating and cooling to a range are there anywhere in the range."""
    await _set(hass, _band(before), state="heat_cool")
    handed, unsub = await _attach(hass)

    await _set(hass, _band(after), state="heat_cool")
    unsub()

    assert bool(handed) is fires


@pytest.mark.parametrize(
    ("state", "after", "fires"),
    [("heat_cool", 21.0, True), ("heat", 21.0, False), ("heat", 23.0, True)],
    ids=["band in heat_cool", "setpoint in heat", "setpoint reached in heat"],
)
async def test_a_thermostat_reporting_both_follows_its_mode(
    hass: HomeAssistant, state: str, after: float, *, fires: bool
) -> None:
    """Both are reported whatever the mode, and the mode says which applies."""
    both = {"temperature": 23.0, "target_temp_low": 20.0, "target_temp_high": 22.0}
    await _set(hass, {"current_temperature": 18.0, **both}, state=state)
    handed, unsub = await _attach(hass)

    await _set(hass, {"current_temperature": after, **both}, state=state)
    unsub()

    assert bool(handed) is fires


async def test_a_water_heater_reaches_its_target_too(hass: HomeAssistant) -> None:
    """The water is hot."""
    boiler = "water_heater.boiler"
    await _set(hass, _heating(40.0, target=55.0), state="eco", entity_id=boiler)
    handed, unsub = await _attach(hass, {"entity_id": boiler})

    await _set(hass, _heating(55.0, target=55.0), state="eco", entity_id=boiler)
    unsub()

    assert len(handed) == 1


async def test_only_thermostats_and_water_heaters_in_an_area_count(
    hass: HomeAssistant,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """An area holds all sorts, whatever their attributes happen to be called."""
    area = area_registry.async_create("Bathroom")
    thermostat = entity_registry.async_get_or_create("climate", "demo", "bath")
    lookalike = entity_registry.async_get_or_create("sensor", "demo", "lookalike")
    for entry in (thermostat, lookalike):
        entity_registry.async_update_entity(entry.entity_id, area_id=area.id)
        await _set(hass, _heating(19.0), entity_id=entry.entity_id)

    handed, unsub = await _attach(hass, {"area_id": area.id})

    await _set(hass, _heating(21.0), entity_id=lookalike.entity_id)
    await _set(hass, _heating(21.0), entity_id=thermostat.entity_id)
    unsub()

    assert [payload["entity_id"] for payload, _context in handed] == [
        thermostat.entity_id
    ]


async def test_it_carries_the_context_of_the_change(hass: HomeAssistant) -> None:
    """Whatever wrote the reading is on it, like every other state trigger."""
    await _set(hass, _heating(19.0))
    handed, unsub = await _attach(hass)

    theirs = Context()
    await _set(hass, _heating(21.0), context=theirs)
    unsub()

    _payload, context = handed[0]
    assert context is theirs
