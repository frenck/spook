"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.components.homeassistant.exposed_entities import (
    KNOWN_ASSISTANTS,
    async_expose_entity,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_ASSISTANTS = "assistants"


class SpookService(AbstractSpookAdminService):
    """Service to unexpose entities from voice assistants."""

    domain = DOMAIN
    service = "unexpose_entity"
    schema = {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(CONF_ASSISTANTS): vol.All(
            cv.ensure_list, [vol.In(KNOWN_ASSISTANTS)]
        ),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)

        for entity_id in call.data[ATTR_ENTITY_ID]:
            if (
                self.hass.states.get(entity_id) is None
                and entity_registry.async_get(entity_id) is None
            ):
                msg = f"Unknown entity: {entity_id}"
                raise HomeAssistantError(msg)

            for assistant in call.data[CONF_ASSISTANTS]:
                should_expose = False
                async_expose_entity(self.hass, assistant, entity_id, should_expose)
