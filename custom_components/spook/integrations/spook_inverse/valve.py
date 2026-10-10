"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN,
    ValveEntity,
    ValveEntityFeature,
    ValveState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_STOP_VALVE,
)
from homeassistant.core import HomeAssistant, State, callback

from .entity import InverseEntity, swapped_features

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

# What this inverse knows how to pass on. Anything else a valve can do, it
# would claim to do and then fail at.
_HANDLED_FEATURES = (
    ValveEntityFeature.OPEN
    | ValveEntityFeature.CLOSE
    | ValveEntityFeature.SET_POSITION
    | ValveEntityFeature.STOP
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize inverse config entry."""
    # The source is resolved by the entity itself, which stays unavailable
    # rather than failing to set up when the source is not there.
    async_add_entities([InverseValve(hass, config_entry)])


class InverseValve(InverseEntity, ValveEntity):  # pylint: disable=too-many-instance-attributes
    """Inverse valve.

    A valve that reports its position leaves whether it is closed to that
    position, the way Home Assistant does for any valve: closed is exactly 0
    and open is anything above it. So a source a third open is two thirds
    open upside down, and the inverse is closed only when the source is all
    the way open. A valve that only knows open or closed has just that turned
    around.
    """

    _attr_reports_position = False

    @callback
    def async_update_state(self, state: State) -> None:
        """Query the source and determine the valve state."""
        self._attr_supported_features = swapped_features(
            ValveEntityFeature(state.attributes.get(ATTR_SUPPORTED_FEATURES) or 0)
            & _HANDLED_FEATURES,
            ValveEntityFeature.OPEN,
            ValveEntityFeature.CLOSE,
        )
        self._attr_is_opening = state.state == ValveState.CLOSING
        self._attr_is_closing = state.state == ValveState.OPENING

        if (position := state.attributes.get(ATTR_CURRENT_POSITION)) is not None:
            self._attr_reports_position = True
            self._attr_current_valve_position = 100 - position
            self._attr_is_closed = position == 100  # noqa: PLR2004
            return

        self._attr_reports_position = False
        self._attr_current_valve_position = None
        self._attr_is_closed = None
        if state.state == ValveState.OPEN:
            self._attr_is_closed = True
        elif state.state == ValveState.CLOSED:
            self._attr_is_closed = False

    async def async_open_valve(self, **_: Any) -> None:
        """Open the valve."""
        await self._async_call(SERVICE_CLOSE_VALVE)

    async def async_close_valve(self, **_: Any) -> None:
        """Close the valve."""
        await self._async_call(SERVICE_OPEN_VALVE)

    async def async_set_valve_position(self, position: int) -> None:
        """Move the valve to a specific position."""
        await self._async_call(
            SERVICE_SET_VALVE_POSITION, {ATTR_POSITION: 100 - position}
        )

    async def async_stop_valve(self, **_: Any) -> None:
        """Stop the valve."""
        await self._async_call(SERVICE_STOP_VALVE)

    async def _async_call(
        self,
        service: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Have the source do it."""
        await self.hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: self._entity_id, **(data or {})},
            blocking=True,
            context=self._context,
        )
