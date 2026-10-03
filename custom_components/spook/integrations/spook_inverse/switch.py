"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback, split_entity_id

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
    # The source is resolved by the entity itself, which stays unavailable
    # rather than failing to set up when the source is not there.
    async_add_entities([InverseSwitch(hass, config_entry)])


class InverseSwitch(InverseEntity, SwitchEntity):
    """Inverse switch.

    Its source can be an on/off helper or a light as well, so it is told what
    to do in its own terms: a light is turned off with the light actions.
    """

    @callback
    def async_update_state(self, state: State) -> None:
        """Query the source and determine the switch state."""
        if state.state == STATE_UNKNOWN:
            self._attr_is_on = None
        else:
            self._attr_is_on = state.state != STATE_ON

    async def async_turn_on(self, **_: Any) -> None:
        """Turn the entity on."""
        await self.hass.services.async_call(
            split_entity_id(self._entity_id)[0],
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **_: Any) -> None:
        """Turn the entity off."""
        await self.hass.services.async_call(
            split_entity_id(self._entity_id)[0],
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_toggle(self, **_: Any) -> None:
        """Toggle the entity."""
        await self.hass.services.async_call(
            split_entity_id(self._entity_id)[0],
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )
