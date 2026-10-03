"""Tests for the inverse cover."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)
import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, CONF_ENTITY_ID
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES

from custom_components.spook.integrations.spook_inverse import MIGRATION_MINOR_VERSION
from custom_components.spook.integrations.spook_inverse.const import (
    CONF_HIDE_SOURCE,
    CONF_INVERSE_POSITION,
    CONF_INVERSE_TILT,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_SOURCE = "cover.blinds"

_EVERYTHING = (
    CoverEntityFeature.OPEN
    | CoverEntityFeature.CLOSE
    | CoverEntityFeature.SET_POSITION
    | CoverEntityFeature.STOP
    | CoverEntityFeature.OPEN_TILT
    | CoverEntityFeature.CLOSE_TILT
    | CoverEntityFeature.STOP_TILT
    | CoverEntityFeature.SET_TILT_POSITION
)


def _blinds(hass: HomeAssistant, state: str, **attributes: Any) -> None:
    """Put the source cover in this state."""
    hass.states.async_set(
        _SOURCE,
        state,
        {ATTR_SUPPORTED_FEATURES: _EVERYTHING, **attributes},
    )


async def _inverse(
    hass: HomeAssistant,
    *,
    inverse_position: bool = True,
    inverse_tilt: bool = False,
) -> str:
    """Set an inverse of the blinds up for real, and return its entity ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inverted blinds",
        version=1,
        minor_version=MIGRATION_MINOR_VERSION,
        options={
            CONF_ENTITY_ID: _SOURCE,
            CONF_HIDE_SOURCE: False,
            CONF_INVERSE_POSITION: inverse_position,
            CONF_INVERSE_TILT: inverse_tilt,
            "inverse_type": "cover",
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
        # A third open is two thirds open upside down, not closed. Closed is
        # exactly 0 and open is everything above it, so they do not mirror.
        (CoverState.OPEN, 30, CoverState.OPEN, 70),
        (CoverState.OPEN, 100, CoverState.CLOSED, 0),
        (CoverState.CLOSED, 0, CoverState.OPEN, 100),
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
    _blinds(hass, source_state, **{ATTR_CURRENT_POSITION: source_position})
    inverse = await _inverse(hass)

    inverted = hass.states.get(inverse)
    assert inverted.state == state
    assert inverted.attributes[ATTR_CURRENT_POSITION] == position


@pytest.mark.parametrize(
    ("source_state", "state"),
    [
        (CoverState.OPEN, CoverState.CLOSED),
        (CoverState.CLOSED, CoverState.OPEN),
        (CoverState.OPENING, CoverState.CLOSING),
        (CoverState.CLOSING, CoverState.OPENING),
    ],
)
async def test_a_cover_without_a_position_is_turned_around(
    hass: HomeAssistant,
    source_state: str,
    state: str,
) -> None:
    """Test a cover that is only open or closed has just that reversed."""
    hass.states.async_set(
        _SOURCE,
        source_state,
        {ATTR_SUPPORTED_FEATURES: CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE},
    )
    inverse = await _inverse(hass)

    assert hass.states.get(inverse).state == state


async def test_what_it_can_do_is_turned_around_too(hass: HomeAssistant) -> None:
    """Test a cover that can only open is one that can only close, inverted.

    And whatever the inverse cannot pass on, it does not claim either.
    """
    hass.states.async_set(
        _SOURCE,
        CoverState.CLOSED,
        {ATTR_SUPPORTED_FEATURES: CoverEntityFeature.OPEN | 1024},
    )
    inverse = await _inverse(hass)

    assert hass.states.get(inverse).attributes[ATTR_SUPPORTED_FEATURES] == (
        CoverEntityFeature.CLOSE
    )


async def test_the_tilt_is_left_alone_unless_asked(hass: HomeAssistant) -> None:
    """Test inverting the position does not turn the slats around as well."""
    _blinds(
        hass,
        CoverState.OPEN,
        **{ATTR_CURRENT_POSITION: 30, ATTR_CURRENT_TILT_POSITION: 20},
    )
    inverse = await _inverse(hass)

    assert hass.states.get(inverse).attributes[ATTR_CURRENT_TILT_POSITION] == 20  # noqa: PLR2004


async def test_only_the_tilt_can_be_inverted(hass: HomeAssistant) -> None:
    """Test slats that tilt the wrong way, on blinds that are otherwise fine."""
    _blinds(
        hass,
        CoverState.OPEN,
        **{ATTR_CURRENT_POSITION: 30, ATTR_CURRENT_TILT_POSITION: 20},
    )
    inverse = await _inverse(hass, inverse_position=False, inverse_tilt=True)

    inverted = hass.states.get(inverse)
    assert inverted.state == CoverState.OPEN
    assert inverted.attributes[ATTR_CURRENT_POSITION] == 30  # noqa: PLR2004
    assert inverted.attributes[ATTR_CURRENT_TILT_POSITION] == 80  # noqa: PLR2004


@pytest.mark.parametrize(
    ("method", "data", "expected_service", "expected_data"),
    [
        ("async_open_cover", {}, "close_cover", {}),
        ("async_close_cover", {}, "open_cover", {}),
        ("async_stop_cover", {}, "stop_cover", {}),
        (
            "async_set_cover_position",
            {"position": 30},
            "set_cover_position",
            {"position": 70},
        ),
        ("async_open_cover_tilt", {}, "close_cover_tilt", {}),
        ("async_close_cover_tilt", {}, "open_cover_tilt", {}),
        ("async_stop_cover_tilt", {}, "stop_cover_tilt", {}),
        (
            "async_set_cover_tilt_position",
            {"tilt_position": 25},
            "set_cover_tilt_position",
            {"tilt_position": 75},
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

    Asked of the entity itself: standing in for the source's cover actions
    stands in for the inverse's own as well, since they are the same actions.
    """
    _blinds(
        hass,
        CoverState.OPEN,
        **{ATTR_CURRENT_POSITION: 50, ATTR_CURRENT_TILT_POSITION: 50},
    )
    inverse = await _inverse(hass, inverse_tilt=True)
    entity = hass.data[DATA_INSTANCES]["cover"].get_entity(inverse)
    calls = async_mock_service(hass, "cover", expected_service)

    await getattr(entity, method)(**data)

    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: _SOURCE, **expected_data}


@pytest.mark.parametrize(
    ("method", "expected_service"),
    [
        # All the way open is, upside down, closed: toggling opens it, which
        # the source does by closing.
        ("async_toggle", "close_cover"),
        # Slats tilted all the way are, upside down, flat: toggling tilts them
        # open, which the source does by tilting closed.
        ("async_toggle_tilt", "close_cover_tilt"),
    ],
)
async def test_toggling_goes_the_way_the_inverse_is_facing(
    hass: HomeAssistant,
    method: str,
    expected_service: str,
) -> None:
    """Test a toggle is worked out from the inverse's state, not the source's.

    Toggling is left to Home Assistant's own cover logic, which picks open or
    close from what the inverse shows, and then hands that to the inverse.
    """
    _blinds(
        hass,
        CoverState.OPEN,
        **{ATTR_CURRENT_POSITION: 100, ATTR_CURRENT_TILT_POSITION: 100},
    )
    inverse = await _inverse(hass, inverse_tilt=True)
    entity = hass.data[DATA_INSTANCES]["cover"].get_entity(inverse)
    calls = async_mock_service(hass, "cover", expected_service)

    await getattr(entity, method)()

    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: _SOURCE}
