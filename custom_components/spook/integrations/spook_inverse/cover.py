"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant, State, callback

from .const import CONF_INVERSE_POSITION, CONF_INVERSE_TILT
from .entity import InverseEntity, swapped_features

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

# What this inverse knows how to pass on. Anything else a cover can do, it
# would claim to do and then fail at.
_HANDLED_FEATURES = (
    CoverEntityFeature.OPEN
    | CoverEntityFeature.CLOSE
    | CoverEntityFeature.SET_POSITION
    | CoverEntityFeature.STOP
    | CoverEntityFeature.OPEN_TILT
    | CoverEntityFeature.CLOSE_TILT
    | CoverEntityFeature.STOP_TILT
    | CoverEntityFeature.SET_TILT_POSITION
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize inverse config entry."""
    # The source is resolved by the entity itself, which stays unavailable
    # rather than failing to set up when the source is not there.
    async_add_entities([InverseCover(hass, config_entry)])


class InverseCover(InverseEntity, CoverEntity):  # pylint: disable=too-many-instance-attributes
    """Inverse cover.

    The position decides whether it is closed, not the source's state. Closed
    is a position of exactly 0 and open is anything above it, so the two are
    not each other's mirror image: a source a third open is not, upside down,
    closed. It is two thirds open. Only a source without a position, which can
    only be open or closed, has its state turned around as it is.
    """

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize an inverse cover."""
        super().__init__(hass, config_entry)
        self._inverse_position: bool = config_entry.options.get(
            CONF_INVERSE_POSITION, True
        )
        self._inverse_tilt: bool = config_entry.options.get(CONF_INVERSE_TILT, False)

    @callback
    def async_update_state(self, state: State) -> None:
        """Query the source and determine the cover state."""
        features = (
            CoverEntityFeature(state.attributes.get(ATTR_SUPPORTED_FEATURES) or 0)
            & _HANDLED_FEATURES
        )
        position = state.attributes.get(ATTR_CURRENT_POSITION)
        tilt = state.attributes.get(ATTR_CURRENT_TILT_POSITION)
        opening = state.state == CoverState.OPENING
        closing = state.state == CoverState.CLOSING
        closed: bool | None = None
        if state.state == CoverState.CLOSED:
            closed = True
        elif state.state == CoverState.OPEN:
            closed = False

        if self._inverse_position:
            features = swapped_features(
                features, CoverEntityFeature.OPEN, CoverEntityFeature.CLOSE
            )
            opening, closing = closing, opening
            if position is not None:
                position = 100 - position
                closed = position == 0
            elif closed is not None:
                closed = not closed

        if self._inverse_tilt:
            features = swapped_features(
                features, CoverEntityFeature.OPEN_TILT, CoverEntityFeature.CLOSE_TILT
            )
            if tilt is not None:
                tilt = 100 - tilt

        self._attr_supported_features = features
        self._attr_current_cover_position = position
        self._attr_current_cover_tilt_position = tilt
        self._attr_is_opening = opening
        self._attr_is_closing = closing
        self._attr_is_closed = closed

    async def async_open_cover(self, **_: Any) -> None:
        """Open the cover."""
        await self._async_call(
            SERVICE_CLOSE_COVER if self._inverse_position else SERVICE_OPEN_COVER
        )

    async def async_close_cover(self, **_: Any) -> None:
        """Close the cover."""
        await self._async_call(
            SERVICE_OPEN_COVER if self._inverse_position else SERVICE_CLOSE_COVER
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        await self._async_call(
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 100 - position if self._inverse_position else position},
        )

    async def async_stop_cover(self, **_: Any) -> None:
        """Stop the cover."""
        await self._async_call(SERVICE_STOP_COVER)

    async def async_open_cover_tilt(self, **_: Any) -> None:
        """Open the cover tilt."""
        await self._async_call(
            SERVICE_CLOSE_COVER_TILT if self._inverse_tilt else SERVICE_OPEN_COVER_TILT
        )

    async def async_close_cover_tilt(self, **_: Any) -> None:
        """Close the cover tilt."""
        await self._async_call(
            SERVICE_OPEN_COVER_TILT if self._inverse_tilt else SERVICE_CLOSE_COVER_TILT
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        tilt = kwargs[ATTR_TILT_POSITION]
        await self._async_call(
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_TILT_POSITION: 100 - tilt if self._inverse_tilt else tilt},
        )

    async def async_stop_cover_tilt(self, **_: Any) -> None:
        """Stop the cover tilt."""
        await self._async_call(SERVICE_STOP_COVER_TILT)

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
