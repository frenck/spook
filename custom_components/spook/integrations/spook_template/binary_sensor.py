"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import (
    CONF_STATE_TEMPLATE,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.template import Template, TemplateError, result_as_boolean
from homeassistant.helpers.template_entity import TemplateEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize inverse config entry."""
    async_add_entities([TemplateBinarySensor(hass, config_entry)])


class TemplateBinarySensor(TemplateEntity, BinarySensorEntity, RestoreEntity):
    """Template binary sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize an template entity."""
        super().__init__(
            hass,
            fallback_name=config_entry.title,
            unique_id=config_entry.entry_id,
        )
        self._attr_name = config_entry.title
        self._state_template = Template(config_entry.options[CONF_STATE_TEMPLATE], hass)

    async def async_added_to_hass(self) -> None:
        """Adding this entity to hass."""
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state == STATE_UNAVAILABLE:
                self._attr_available = False

            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._attr_is_on = last_state.state == STATE_ON

        self.add_template_attribute(
            "_attr_is_on",
            self._state_template,
            None,
            self._update_state,
        )

        await super().async_added_to_hass()

    @callback
    def _update_state(self, result: str | TemplateError | None) -> None:
        super()._update_state(result)
        self._attr_is_on = (
            None if isinstance(result, TemplateError) else result_as_boolean(result)
        )
