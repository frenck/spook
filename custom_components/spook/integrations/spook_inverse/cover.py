"""Spook - Not your homie."""
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
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    CoverEntity,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_INVERSE_POSTITION, CONF_INVERSE_TILT
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
    async_add_entities([InverseCover(config_entry)])


class InverseCover(InverseEntity, CoverEntity):
    """Inverse cover."""

    @callback
    # pylint: disable=too-many-branches
    def async_update_state(self, state: State) -> None:  # noqa: C901, PLR0912
        """Query the source and determine the switch state."""
        extra_state_attributes = state.attributes.copy()
        if self.config_entry.options[CONF_INVERSE_POSTITION]:
            if state.state == STATE_OPEN:
                self._attr_is_closed = True
                self._attr_is_opening = False
                self._attr_is_closing = False
            elif state.state == STATE_OPENING:
                self._attr_is_closed = True
                self._attr_is_opening = False
                self._attr_is_closing = True
            elif state.state == STATE_CLOSING:
                self._attr_is_closed = False
                self._attr_is_opening = True
                self._attr_is_closing = False
            elif state.state == STATE_CLOSED:
                self._attr_is_closed = False
                self._attr_is_opening = False
                self._attr_is_closing = False

            if (
                current_position := extra_state_attributes.pop(
                    ATTR_CURRENT_POSITION,
                    None,
                )
            ) is not None:
                self._attr_current_cover_position = 100 - current_position
            else:
                self._attr_current_cover_position = None
        else:
            if state.state == STATE_OPEN:
                self._attr_is_closed = False
                self._attr_is_opening = False
                self._attr_is_closing = False
            elif state.state == STATE_OPENING:
                self._attr_is_closed = False
                self._attr_is_opening = True
                self._attr_is_closing = False
            elif state.state == STATE_CLOSING:
                self._attr_is_closed = True
                self._attr_is_opening = False
                self._attr_is_closing = True
            elif state.state == STATE_CLOSED:
                self._attr_is_closed = True
                self._attr_is_opening = False
                self._attr_is_closing = False

            self._attr_current_cover_position = extra_state_attributes.pop(
                ATTR_CURRENT_POSITION,
                None,
            )

        if self.config_entry.options[CONF_INVERSE_TILT]:
            if (
                current_tilt_position := extra_state_attributes.pop(
                    ATTR_CURRENT_TILT_POSITION,
                    None,
                )
            ) is not None:
                self._attr_current_cover_tilt_position = 100 - current_tilt_position
            else:
                self._attr_current_cover_tilt_position = None
        else:
            self._attr_current_cover_tilt_position = extra_state_attributes.pop(
                ATTR_CURRENT_TILT_POSITION,
                None,
            )

        self._attr_extra_state_attributes = extra_state_attributes

    async def async_open_cover(self, **_: Any) -> None:
        """Open the cover."""
        service = SERVICE_OPEN_COVER
        if self.config_entry.options[CONF_INVERSE_POSTITION]:
            service = SERVICE_CLOSE_COVER
        await self.hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_close_cover(self, **_: Any) -> None:
        """Close cover."""
        service = SERVICE_CLOSE_COVER
        if self.config_entry.options[CONF_INVERSE_POSTITION]:
            service = SERVICE_OPEN_COVER
        await self.hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_toggle(self, **_: Any) -> None:
        """Toggle the entity."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if self.config_entry.options[CONF_INVERSE_POSTITION]:
            position = 100 - position
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: self._entity_id, ATTR_POSITION: position},
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
        service = SERVICE_OPEN_COVER_TILT
        if self.config_entry.options[CONF_INVERSE_TILT]:
            service = SERVICE_CLOSE_COVER_TILT
        await self.hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_close_cover_tilt(self, **_: Any) -> None:
        """Close the cover tilt."""
        service = SERVICE_CLOSE_COVER_TILT
        if self.config_entry.options[CONF_INVERSE_TILT]:
            service = SERVICE_OPEN_COVER_TILT
        await self.hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        position = kwargs[ATTR_TILT_POSITION]
        if self.config_entry.options[CONF_INVERSE_TILT]:
            position = 100 - position
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: self._entity_id, ATTR_TILT_POSITION: position},
            blocking=True,
            context=self._context,
        )

    async def async_stop_cover_tilt(self, **_: Any) -> None:
        """Stop the cover."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_COVER_TILT,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_toggle_tilt(self, **_: Any) -> None:
        """Toggle the entity."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_TOGGLE_COVER_TILT,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )
