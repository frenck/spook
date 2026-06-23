"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_DISPLAY_PRECISION = "display_precision"


class SpookService(AbstractSpookAdminService):
    """Service to set a sensor display precision."""

    domain = DOMAIN
    service = "set_display_precision"
    schema = {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(CONF_DISPLAY_PRECISION): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        ),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)
        display_precision = call.data[CONF_DISPLAY_PRECISION]

        for entity_id in call.data[ATTR_ENTITY_ID]:
            if (
                split_entity_id(entity_id)[0] != DOMAIN
                or entity_registry.async_get(entity_id) is None
            ):
                msg = f"Unknown sensor entity: {entity_id}"
                raise HomeAssistantError(msg)

            sensor_options = dict(
                entity_registry.async_get(entity_id).options.get(DOMAIN, {})  # type: ignore[union-attr]
            )
            sensor_options[CONF_DISPLAY_PRECISION] = display_precision
            entity_registry.async_update_entity_options(
                entity_id, DOMAIN, sensor_options
            )
