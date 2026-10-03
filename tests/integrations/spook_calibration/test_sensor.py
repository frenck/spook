"""Tests for the calibration sensor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Context
from homeassistant.data_entry_flow import FlowResultType

from custom_components.spook.integrations.spook_calibration.const import (
    CONF_FACTOR,
    CONF_OFFSET,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er

_SOURCE = "sensor.living_room_temperature"
_SENSOR = "sensor.living_room_calibrated"
_TEMPERATURE = {
    ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
    ATTR_DEVICE_CLASS: "temperature",
    "state_class": "measurement",
}


async def _set_up(
    hass: HomeAssistant, *, offset: float = 0, factor: float = 1
) -> MockConfigEntry:
    """Set the helper up for real."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room calibrated",
        options={
            CONF_NAME: "Living room calibrated",
            CONF_ENTITY_ID: _SOURCE,
            CONF_OFFSET: offset,
            CONF_FACTOR: factor,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_it_corrects_the_source(hass: HomeAssistant) -> None:
    """Test the offset is added, and the source's unit and classes kept."""
    hass.states.async_set(_SOURCE, "21.3", _TEMPERATURE)
    await _set_up(hass, offset=-1.5)

    state = hass.states.get(_SENSOR)
    assert state.state == "19.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == "temperature"
    assert state.attributes["state_class"] == "measurement"


async def test_the_factor_goes_before_the_offset(hass: HomeAssistant) -> None:
    """Test the value is multiplied first, and the offset added after."""
    hass.states.async_set(_SOURCE, "50", {ATTR_UNIT_OF_MEASUREMENT: "%"})
    await _set_up(hass, offset=2, factor=1.1)

    assert hass.states.get(_SENSOR).state == "57.0"


async def test_it_follows_the_source(hass: HomeAssistant) -> None:
    """Test a new value is corrected, under the change that caused it."""
    hass.states.async_set(_SOURCE, "21.3", _TEMPERATURE)
    await _set_up(hass, offset=-1.5)

    context = Context()
    hass.states.async_set(_SOURCE, "22.1", _TEMPERATURE, context=context)
    await hass.async_block_till_done()

    state = hass.states.get(_SENSOR)
    assert state.state == "20.6"
    assert state.context.id == context.id


async def test_without_a_number_there_is_nothing_to_correct(
    hass: HomeAssistant,
) -> None:
    """Test unavailable, unknown and text make the helper unavailable."""
    hass.states.async_set(_SOURCE, "21.3", _TEMPERATURE)
    await _set_up(hass, offset=-1.5)

    for not_a_number in (STATE_UNAVAILABLE, STATE_UNKNOWN, "warm", "nan"):
        hass.states.async_set(_SOURCE, not_a_number, _TEMPERATURE)
        await hass.async_block_till_done()
        assert hass.states.get(_SENSOR).state == STATE_UNAVAILABLE, not_a_number

    hass.states.async_set(_SOURCE, "21.3", _TEMPERATURE)
    await hass.async_block_till_done()
    assert hass.states.get(_SENSOR).state == "19.8"


async def test_a_missing_source_is_unavailable(hass: HomeAssistant) -> None:
    """Test a source that is not there yet makes no number up."""
    await _set_up(hass, offset=-1.5)

    assert hass.states.get(_SENSOR).state == STATE_UNAVAILABLE


async def test_a_renamed_source_is_followed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the helper keeps correcting the source under its new name."""
    entity_registry.async_get_or_create(
        "sensor", "test", "temperature", suggested_object_id="living_room_temperature"
    )
    hass.states.async_set(_SOURCE, "21.3", _TEMPERATURE)
    entry = await _set_up(hass, offset=-1.5)

    entity_registry.async_update_entity(
        _SOURCE, new_entity_id="sensor.lounge_temperature"
    )
    await hass.async_block_till_done()
    hass.states.async_set("sensor.lounge_temperature", "23.0", _TEMPERATURE)
    await hass.async_block_till_done()

    assert entry.options[CONF_ENTITY_ID] == "sensor.lounge_temperature"
    assert hass.states.get(_SENSOR).state == "21.5"


async def test_the_config_flow_creates_the_helper(hass: HomeAssistant) -> None:
    """Test the flow takes a source and its correction."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Calibrated", CONF_ENTITY_ID: _SOURCE, CONF_OFFSET: -1.5},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Calibrated"
    assert result["options"] == {
        CONF_NAME: "Calibrated",
        CONF_ENTITY_ID: _SOURCE,
        CONF_OFFSET: -1.5,
        CONF_FACTOR: 1,
    }
