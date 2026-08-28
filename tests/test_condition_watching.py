"""Tests for watching a condition turn true."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import voluptuous as vol

from custom_components.spook.condition_watching import (
    BACKSTOP,
    async_condition_watcher,
    async_validate_condition,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

GATE = {"condition": "state", "entity_id": "input_boolean.gate", "state": "on"}
GATE_TEMPLATE = {
    "condition": "template",
    "value_template": "{{ is_state('input_boolean.gate', 'on') }}",
}


async def _watching(
    hass: HomeAssistant,
    config: ConfigType,
) -> tuple[object, list[int]]:
    """Start watching a condition and record every turn."""
    turns: list[int] = []
    watcher = await async_condition_watcher(
        hass, await async_validate_condition(hass, config), lambda: turns.append(1)
    )
    watcher.async_start()
    return watcher, turns


async def test_it_reports_the_turn_and_nothing_else(hass: HomeAssistant) -> None:
    """False to true is the event. True to false is not, and neither is staying."""
    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    watcher, turns = await _watching(hass, GATE)
    assert watcher.met is False
    assert not turns

    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert watcher.met is True
    assert len(turns) == 1

    # Still true, written again: not a turn.
    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert len(turns) == 1

    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()
    assert watcher.met is False
    assert len(turns) == 1, "reported going false as a turn"

    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert len(turns) == TWICE

    watcher.async_stop()


async def test_a_condition_already_true_is_not_a_turn(hass: HomeAssistant) -> None:
    """Starting to watch something that is already true changes nothing.

    Callers that care about the current value ask for it, which is what keeps
    the trigger from firing on every reload.
    """
    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()

    watcher, turns = await _watching(hass, GATE)

    assert watcher.met is True
    assert not turns, "reported a turn for something that was already true"

    watcher.async_stop()


async def test_a_template_condition_is_found_by_the_backstop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A template condition names no entities that can be read off the config.

    So nothing announces it, and the timer is the only thing that finds it.
    This is why there is a timer at all.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    watcher, turns = await _watching(hass, GATE_TEMPLATE)

    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert not turns, "expected the template to go unnoticed until the backstop"

    freezer.tick(BACKSTOP + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(turns) == 1, "the backstop never asked again"

    watcher.async_stop()


async def test_the_backstop_runs_even_with_entities_to_watch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Half a condition can announce itself while the other half cannot.

    An `and` of a state and a template hands over the state's entity, so it
    would be easy to conclude there is nothing left to poll for. The template
    half still needs asking.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    hass.states.async_set("input_boolean.gate", "on")
    hass.states.async_set("sensor.temp", "10")
    await hass.async_block_till_done()

    watcher, turns = await _watching(
        hass,
        {
            "condition": "and",
            "conditions": [
                GATE,
                {
                    "condition": "template",
                    "value_template": "{{ states('sensor.temp') | int > 20 }}",
                },
            ],
        },
    )
    assert watcher.met is False

    # Only the template half changes, so only the backstop can find it.
    hass.states.async_set("sensor.temp", "25")
    await hass.async_block_till_done()

    freezer.tick(BACKSTOP + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(turns) == 1, "stopped polling because there were entities to watch"

    watcher.async_stop()


async def test_a_condition_that_cannot_answer_counts_as_false(
    hass: HomeAssistant,
) -> None:
    """A missing entity makes a state condition raise, which is not true.

    Worth holding: the alternative is the watcher falling over on something
    Home Assistant considers an ordinary state of affairs.
    """
    watcher, turns = await _watching(
        hass,
        {
            "condition": "state",
            "entity_id": "input_boolean.never_existed",
            "state": "on",
        },
    )

    assert watcher.met is False
    assert not turns

    watcher.async_stop()


async def test_a_condition_written_the_short_way_is_accepted(
    hass: HomeAssistant,
) -> None:
    """People write a single entity, not a list, and a template as a string.

    Validation turns both into what a checker can use. Without it the checker
    raises on every single check instead of answering.
    """
    validated = await async_validate_condition(hass, GATE)
    assert validated["entity_id"] == ["input_boolean.gate"]

    validated = await async_validate_condition(hass, GATE_TEMPLATE)
    assert not isinstance(validated["value_template"], str)


async def test_a_malformed_condition_is_refused(hass: HomeAssistant) -> None:
    """The wrong shape is caught by the schema."""
    with pytest.raises(vol.Invalid):
        await async_validate_condition(hass, {"no": "condition here"})


async def test_a_condition_that_does_not_exist_is_refused(
    hass: HomeAssistant,
) -> None:
    """An unknown condition type is Home Assistant's own refusal, not the schema's.

    Worth pinning the type, because it decides what a caller has to catch:
    this one arrives as a `HomeAssistantError` rather than a `vol.Invalid`.
    """
    with pytest.raises(HomeAssistantError, match="Invalid condition"):
        await async_validate_condition(hass, {"condition": "not_a_condition"})


TWICE = 2
