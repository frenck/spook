"""Tests for the inverse valve."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)
import pytest

from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ValveEntityFeature,
    ValveState,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, CONF_ENTITY_ID
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES

from custom_components.spook.integrations.spook_inverse import MIGRATION_MINOR_VERSION
from custom_components.spook.integrations.spook_inverse.const import (
    CONF_HIDE_SOURCE,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_SOURCE = "valve.irrigation"

_EVERYTHING = (
    ValveEntityFeature.OPEN
    | ValveEntityFeature.CLOSE
    | ValveEntityFeature.SET_POSITION
    | ValveEntityFeature.STOP
)


async def _inverse(hass: HomeAssistant) -> str:
    """Set an inverse of the valve up for real, and return its entity ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inverted irrigation",
        version=1,
        minor_version=MIGRATION_MINOR_VERSION,
        options={
            CONF_ENTITY_ID: _SOURCE,
            CONF_HIDE_SOURCE: False,
            "inverse_type": "valve",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    (inverse,) = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    return inverse.entity_id


@pytest.mark.parametrize(
    ("source_state", "source_position", "state", "position"),
    [
        # A third open is two thirds open upside down, not closed.
        (ValveState.OPEN, 30, ValveState.OPEN, 70),
        (ValveState.OPEN, 100, ValveState.CLOSED, 0),
        (ValveState.CLOSED, 0, ValveState.OPEN, 100),
    ],
)
async def test_the_position_decides_whether_it_is_closed(
    hass: HomeAssistant,
    source_state: str,
    source_position: int,
    state: str,
    position: int,
) -> None:
    """Test the inverse is closed only when the source is all the way open."""
    hass.states.async_set(
        _SOURCE,
        source_state,
        {ATTR_SUPPORTED_FEATURES: _EVERYTHING, ATTR_CURRENT_POSITION: source_position},
    )
    inverse = await _inverse(hass)

    inverted = hass.states.get(inverse)
    assert inverted.state == state
    assert inverted.attributes[ATTR_CURRENT_POSITION] == position


@pytest.mark.parametrize(
    ("source_state", "state"),
    [
        (ValveState.OPEN, ValveState.CLOSED),
        (ValveState.CLOSED, ValveState.OPEN),
        (ValveState.OPENING, ValveState.CLOSING),
        (ValveState.CLOSING, ValveState.OPENING),
    ],
)
async def test_a_valve_without_a_position_is_turned_around(
    hass: HomeAssistant,
    source_state: str,
    state: str,
) -> None:
    """Test a valve that is only open or closed has just that reversed."""
    hass.states.async_set(
        _SOURCE,
        source_state,
        {ATTR_SUPPORTED_FEATURES: ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE},
    )
    inverse = await _inverse(hass)

    assert hass.states.get(inverse).state == state


async def test_what_it_can_do_is_turned_around_too(hass: HomeAssistant) -> None:
    """Test a valve that can only open is one that can only close, inverted."""
    hass.states.async_set(
        _SOURCE,
        ValveState.CLOSED,
        {ATTR_SUPPORTED_FEATURES: ValveEntityFeature.OPEN | 1024},
    )
    inverse = await _inverse(hass)

    assert hass.states.get(inverse).attributes[ATTR_SUPPORTED_FEATURES] == (
        ValveEntityFeature.CLOSE
    )


@pytest.mark.parametrize(
    ("method", "data", "expected_service", "expected_data"),
    [
        ("async_open_valve", {}, "close_valve", {}),
        ("async_close_valve", {}, "open_valve", {}),
        ("async_stop_valve", {}, "stop_valve", {}),
        (
            "async_set_valve_position",
            {"position": 30},
            "set_valve_position",
            {"position": 70},
        ),
    ],
)
async def test_what_it_is_told_reaches_the_source_turned_around(
    hass: HomeAssistant,
    method: str,
    data: dict[str, Any],
    expected_service: str,
    expected_data: dict[str, Any],
) -> None:
    """Test every action lands on the source, reversed where it has a direction.

    Asked of the entity itself: standing in for the source's valve actions
    stands in for the inverse's own as well, since they are the same actions.
    """
    hass.states.async_set(
        _SOURCE,
        ValveState.OPEN,
        {ATTR_SUPPORTED_FEATURES: _EVERYTHING, ATTR_CURRENT_POSITION: 50},
    )
    inverse = await _inverse(hass)
    entity = hass.data[DATA_INSTANCES]["valve"].get_entity(inverse)
    calls = async_mock_service(hass, "valve", expected_service)

    await getattr(entity, method)(**data)

    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: _SOURCE, **expected_data}


async def test_toggling_goes_the_way_the_inverse_is_facing(
    hass: HomeAssistant,
) -> None:
    """Test a toggle is worked out from the inverse's state, not the source's.

    All the way open is, upside down, closed: toggling opens it, which Home
    Assistant does for a valve with a position by setting it to 100, and the
    source gets that as 0.
    """
    hass.states.async_set(
        _SOURCE,
        ValveState.OPEN,
        {ATTR_SUPPORTED_FEATURES: _EVERYTHING, ATTR_CURRENT_POSITION: 100},
    )
    inverse = await _inverse(hass)
    entity = hass.data[DATA_INSTANCES]["valve"].get_entity(inverse)
    calls = async_mock_service(hass, "valve", "set_valve_position")

    await entity.async_toggle()

    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: _SOURCE, "position": 0}
