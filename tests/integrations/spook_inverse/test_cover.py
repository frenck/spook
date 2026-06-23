"""Tests for the Spook inverse cover platform."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import State

from custom_components.spook.integrations.spook_inverse.const import (
    CONF_HIDE_SOURCE,
    DOMAIN,
)
from custom_components.spook.integrations.spook_inverse.cover import InverseCover

INVERTED_POSITION = 75
INVERTED_TILT_POSITION = 40

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall


def _create_inverse_cover(hass: HomeAssistant) -> InverseCover:
    """Create an inverse cover entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inverse cover",
        options={
            CONF_ENTITY_ID: "cover.source",
            CONF_HIDE_SOURCE: False,
            "inverse_type": Platform.COVER,
        },
    )
    return InverseCover(hass, entry)


def test_inverse_cover_inverts_state_and_position(hass: HomeAssistant) -> None:
    """Test inverse cover state and position are inverted."""
    cover = _create_inverse_cover(hass)

    cover.async_update_state(
        State(
            "cover.source",
            STATE_OPEN,
            {
                ATTR_CURRENT_POSITION: 25,
                ATTR_CURRENT_TILT_POSITION: 60,
            },
        )
    )

    assert cover.is_closed is True
    assert cover.is_opening is False
    assert cover.is_closing is False
    assert cover.current_cover_position == INVERTED_POSITION
    assert cover.current_cover_tilt_position == INVERTED_TILT_POSITION


def test_inverse_cover_inverts_opening_and_closing(hass: HomeAssistant) -> None:
    """Test inverse cover swaps opening and closing."""
    cover = _create_inverse_cover(hass)

    cover.async_update_state(State("cover.source", STATE_OPENING))

    assert cover.is_opening is False
    assert cover.is_closing is True

    cover.async_update_state(State("cover.source", STATE_CLOSING))

    assert cover.is_opening is True
    assert cover.is_closing is False


def test_inverse_cover_handles_closed_and_unknown_state(hass: HomeAssistant) -> None:
    """Test inverse cover handles closed and unknown source states."""
    cover = _create_inverse_cover(hass)

    cover.async_update_state(State("cover.source", STATE_CLOSED))

    assert cover.is_closed is False

    cover.async_update_state(State("cover.source", STATE_UNKNOWN))

    assert cover.is_closed is None


async def test_inverse_cover_calls_inverse_services(hass: HomeAssistant) -> None:
    """Test inverse cover calls the opposite source cover services."""
    calls: list[tuple[str, dict[str, Any]]] = []

    async def _service_handler(call: ServiceCall) -> None:
        """Record service calls."""
        calls.append((call.service, dict(call.data)))

    for service in (
        SERVICE_CLOSE_COVER,
        SERVICE_OPEN_COVER,
        SERVICE_SET_COVER_POSITION,
        SERVICE_STOP_COVER,
        SERVICE_CLOSE_COVER_TILT,
        SERVICE_OPEN_COVER_TILT,
        SERVICE_SET_COVER_TILT_POSITION,
        SERVICE_STOP_COVER_TILT,
    ):
        hass.services.async_register(COVER_DOMAIN, service, _service_handler)

    cover = _create_inverse_cover(hass)

    await cover.async_open_cover()
    await cover.async_close_cover()
    await cover.async_set_cover_position(position=30)
    await cover.async_stop_cover()
    await cover.async_open_cover_tilt()
    await cover.async_close_cover_tilt()
    await cover.async_set_cover_tilt_position(tilt_position=40)
    await cover.async_stop_cover_tilt()

    assert calls == [
        (SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: "cover.source"}),
        (SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.source"}),
        (
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: "cover.source", ATTR_POSITION: 70},
        ),
        (SERVICE_STOP_COVER, {ATTR_ENTITY_ID: "cover.source"}),
        (SERVICE_CLOSE_COVER_TILT, {ATTR_ENTITY_ID: "cover.source"}),
        (SERVICE_OPEN_COVER_TILT, {ATTR_ENTITY_ID: "cover.source"}),
        (
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: "cover.source", ATTR_TILT_POSITION: 60},
        ),
        (SERVICE_STOP_COVER_TILT, {ATTR_ENTITY_ID: "cover.source"}),
    ]
