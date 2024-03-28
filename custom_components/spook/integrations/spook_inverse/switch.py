"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
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
    async_add_entities([InverseSwitch(config_entry)])


class InverseSwitch(InverseEntity, SwitchEntity):
    """Inverse switch."""

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
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **_: Any) -> None:
        """Turn the entity off."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
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
