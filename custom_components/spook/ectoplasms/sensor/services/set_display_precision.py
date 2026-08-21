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

# The frontend hands this to Intl.NumberFormat as maximumFractionDigits, which
# ECMA-402 caps at 100 and which throws outside that range. A sensor that
# cannot be rendered is a worse outcome than a rejected action call.
MAX_DISPLAY_PRECISION = 100


class SpookService(AbstractSpookAdminService):
    """Sensor service to set how many decimals a sensor shows.

    Home Assistant offers this per entity in the UI only. This is the same
    setting, so it can be applied to a pile of sensors at once.
    """

    domain = DOMAIN
    service = "set_display_precision"
    schema = {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(CONF_DISPLAY_PRECISION): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=MAX_DISPLAY_PRECISION)
        ),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)

        # Resolve every entity before changing any of them. An unknown one
        # halfway down the list would otherwise leave the sensors before it
        # already updated, with nothing saying which.
        entries = []
        for entity_id in call.data[ATTR_ENTITY_ID]:
            entry = entity_registry.async_get(entity_id)
            if entry is None or split_entity_id(entity_id)[0] != DOMAIN:
                msg = f"Unknown sensor entity: {entity_id}"
                raise HomeAssistantError(msg)
            entries.append(entry)

        display_precision = call.data[CONF_DISPLAY_PRECISION]
        for entry in entries:
            # Merged, so a custom unit or any other sensor option survives.
            options = dict(entry.options.get(DOMAIN, {}))
            options[CONF_DISPLAY_PRECISION] = display_precision
            entity_registry.async_update_entity_options(
                entry.entity_id, DOMAIN, options
            )
