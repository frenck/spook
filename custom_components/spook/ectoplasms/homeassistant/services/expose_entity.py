"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.components.homeassistant.exposed_entities import (
    KNOWN_ASSISTANTS,
    async_expose_entity,
)
from homeassistant.const import ATTR_ENTITY_ID, CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_ASSISTANTS = "assistants"


class SpookService(AbstractSpookAdminService):
    """Service to expose entities to voice assistants."""

    domain = DOMAIN
    service = "expose_entity"
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
            if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
                msg = f"Entity cannot be exposed: {entity_id}"
                raise HomeAssistantError(msg)
            if (
                self.hass.states.get(entity_id) is None
                and entity_registry.async_get(entity_id) is None
            ):
                msg = f"Unknown entity: {entity_id}"
                raise HomeAssistantError(msg)

            for assistant in call.data[CONF_ASSISTANTS]:
                should_expose = True
                async_expose_entity(self.hass, assistant, entity_id, should_expose)
