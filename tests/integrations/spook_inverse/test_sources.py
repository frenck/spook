"""Tests for inverting an on/off helper or a light."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.setup import async_setup_component

from custom_components.spook.integrations.spook_inverse import MIGRATION_MINOR_VERSION
from custom_components.spook.integrations.spook_inverse.const import (
    CONF_HIDE_SOURCE,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _inverse(hass: HomeAssistant, inverse_type: str, source: str) -> str:
    """Set an inverse of this kind up for real, and return its entity ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Upside down",
        version=1,
        minor_version=MIGRATION_MINOR_VERSION,
        options={
            CONF_ENTITY_ID: source,
            CONF_HIDE_SOURCE: False,
            "inverse_type": inverse_type,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    (inverse,) = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    return inverse.entity_id


async def test_a_switch_can_be_an_on_off_helper_upside_down(
    hass: HomeAssistant,
) -> None:
    """Test turning the inverse on turns the helper off, with its own actions."""
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"away": {"initial": False}}}
    )
    await hass.async_block_till_done()
    inverse = await _inverse(hass, "switch", "input_boolean.away")
    assert hass.states.get(inverse).state == STATE_ON

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: inverse}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get("input_boolean.away").state == STATE_ON
    assert hass.states.get(inverse).state == STATE_OFF


async def test_a_switch_can_be_a_light_upside_down(hass: HomeAssistant) -> None:
    """Test a light is told what to do with the light actions.

    And what a light can do is not something a switch claims: its features
    mean colours and effects, not anything a switch does.
    """
    hass.states.async_set("light.porch", STATE_OFF, {ATTR_SUPPORTED_FEATURES: 44})
    inverse = await _inverse(hass, "switch", "light.porch")
    entity = hass.data[DATA_INSTANCES]["switch"].get_entity(inverse)
    calls = async_mock_service(hass, "light", "turn_on")

    await entity.async_turn_off()

    assert calls[0].data == {ATTR_ENTITY_ID: "light.porch"}
    assert ATTR_SUPPORTED_FEATURES not in hass.states.get(inverse).attributes


async def test_a_binary_sensor_can_read_an_on_off_helper_upside_down(
    hass: HomeAssistant,
) -> None:
    """Test the inverse reads the helper's state the other way round."""
    hass.states.async_set("input_boolean.away", STATE_ON)
    inverse = await _inverse(hass, "binary_sensor", "input_boolean.away")

    assert hass.states.get(inverse).state == STATE_OFF


async def test_a_source_of_its_own_kind_still_passes_on_its_class(
    hass: HomeAssistant,
) -> None:
    """Test a binary sensor upside down keeps being, say, a door."""
    hass.states.async_set("binary_sensor.door", STATE_ON, {ATTR_DEVICE_CLASS: "door"})
    inverse = await _inverse(hass, "binary_sensor", "binary_sensor.door")

    assert hass.states.get(inverse).attributes[ATTR_DEVICE_CLASS] == "door"
