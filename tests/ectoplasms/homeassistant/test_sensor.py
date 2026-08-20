"""Tests for Spook Home Assistant sensors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.components import automation, counter, group, script, timer

from custom_components.spook.ectoplasms.homeassistant.sensor import SENSORS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

SPOOK_ROOT = Path(__file__).parents[3] / "custom_components" / "spook"


def _value_for_sensor(hass: HomeAssistant, key: str) -> int | None:
    """Return the value for a Spook sensor by key."""
    return next(sensor.value_fn(hass) for sensor in SENSORS if sensor.key == key)


async def test_script_count_excludes_restored_entities(hass: HomeAssistant) -> None:
    """Test restored script entities are not counted."""
    hass.states.async_set("script.active", "off")
    hass.states.async_set("script.restored", "unavailable", {"restored": True})

    assert _value_for_sensor(hass, script.DOMAIN) == 1


async def test_automation_count_excludes_restored_entities(hass: HomeAssistant) -> None:
    """Test restored automation entities are not counted."""
    hass.states.async_set("automation.active", "off")
    hass.states.async_set("automation.restored", "unavailable", {"restored": True})

    assert _value_for_sensor(hass, automation.DOMAIN) == 1


async def test_counter_count(hass: HomeAssistant) -> None:
    """Test counters are counted."""
    counters = ("counter.animals_detected", "counter.doorbell_presses")
    for entity_id in counters:
        hass.states.async_set(entity_id, "0")

    assert _value_for_sensor(hass, counter.DOMAIN) == len(counters)


async def test_group_count(hass: HomeAssistant) -> None:
    """Test groups are counted."""
    hass.states.async_set("group.exterior_lights", "on")

    assert _value_for_sensor(hass, group.DOMAIN) == 1


async def test_timer_count(hass: HomeAssistant) -> None:
    """Test timers are counted."""
    timers = ("timer.kitchen_lighting", "timer.laundry")
    for entity_id in timers:
        hass.states.async_set(entity_id, "idle")

    assert _value_for_sensor(hass, timer.DOMAIN) == len(timers)


def test_every_sensor_has_a_translation() -> None:
    """Test every sensor description has a name to show.

    Without a translation the entity falls back to showing its key, which
    nobody notices until it is on someone's dashboard.
    """
    translations = json.loads((SPOOK_ROOT / "translations" / "en.json").read_text())[
        "entity"
    ]["sensor"]

    missing = [
        sensor.translation_key
        for sensor in SENSORS
        if sensor.translation_key not in translations
    ]

    assert not missing
