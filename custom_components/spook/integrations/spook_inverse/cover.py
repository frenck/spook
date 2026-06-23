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
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er

from .entity import InverseEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize inverse config entry."""
    er.async_validate_entity_id(
        er.async_get(hass),
        config_entry.options[CONF_ENTITY_ID],
    )
    async_add_entities([InverseCover(hass, config_entry)])


class InverseCover(InverseEntity, CoverEntity):
    """Inverse cover."""

    @callback
    def async_update_state(self, state: State) -> None:
        """Query the source and determine the cover state."""
        self._attr_is_opening = state.state == STATE_CLOSING
        self._attr_is_closing = state.state == STATE_OPENING
        if state.state == STATE_UNKNOWN:
            self._attr_is_closed = None
        else:
            self._attr_is_closed = state.state == STATE_OPEN

        self._attr_current_cover_position = self._inverse_position(
            state.attributes.get(ATTR_CURRENT_POSITION)
        )
        self._attr_current_cover_tilt_position = self._inverse_position(
            state.attributes.get(ATTR_CURRENT_TILT_POSITION)
        )

    @staticmethod
    @callback
    def _inverse_position(position: Any) -> int | None:
        """Return the inverse of a cover position."""
        if not isinstance(position, int):
            return None
        return 100 - position

    async def async_open_cover(self, **_: Any) -> None:
        """Open the cover."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_close_cover(self, **_: Any) -> None:
        """Close the cover."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {
                ATTR_ENTITY_ID: self._entity_id,
                ATTR_POSITION: 100 - kwargs[ATTR_POSITION],
            },
            blocking=True,
            context=self._context,
        )

    async def async_stop_cover(self, **_: Any) -> None:
        """Stop the cover."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_open_cover_tilt(self, **_: Any) -> None:
        """Open the cover tilt."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_close_cover_tilt(self, **_: Any) -> None:
        """Close the cover tilt."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {
                ATTR_ENTITY_ID: self._entity_id,
                ATTR_TILT_POSITION: 100 - kwargs[ATTR_TILT_POSITION],
            },
            blocking=True,
            context=self._context,
        )

    async def async_stop_cover_tilt(self, **_: Any) -> None:
        """Stop the cover tilt."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_COVER_TILT,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )
