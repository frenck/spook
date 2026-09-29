"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from ....services import AbstractSpookAdminService
from ..categories import async_resolve_category, async_scope_for_entity

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to add a category to an entity.

    An entity has at most one category per scope, so this replaces whatever
    category it had on that page. That is what picking one in the UI does.
    """

    domain = DOMAIN
    service = "add_category_to_entity"
    schema = {
        vol.Required("category_id"): cv.string,
        vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)

        for entity_id in call.data["entity_id"]:
            if (entity_entry := entity_registry.async_get(entity_id)) is None:
                msg = f"Entity {entity_id} not found"
                raise HomeAssistantError(msg)

            scope = async_scope_for_entity(entity_id)
            category = async_resolve_category(
                self.hass, scope, call.data["category_id"]
            )

            categories = {**entity_entry.categories, scope: category.category_id}
            entity_registry.async_update_entity(entity_id, categories=categories)
