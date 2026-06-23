"""Tests for Spook Home Assistant sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation, script

from custom_components.spook.ectoplasms.homeassistant.sensor import SENSORS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


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
