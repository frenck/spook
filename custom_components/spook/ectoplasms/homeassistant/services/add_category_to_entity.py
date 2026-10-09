"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import config_validation as cv, entity_registry as er

from ....errors import entity_not_found
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

        # Everything is looked up before anything is written. A typo in the
        # last entity should not leave the first ones changed behind an error.
        updates: dict[str, dict[str, str]] = {}
        for entity_id in call.data["entity_id"]:
            if (entity_entry := entity_registry.async_get(entity_id)) is None:
                raise entity_not_found(entity_id)

            scope = async_scope_for_entity(entity_id)
            category = async_resolve_category(
                self.hass, scope, call.data["category_id"]
            )
            updates[entity_id] = {
                **entity_entry.categories,
                scope: category.category_id,
            }

        for entity_id, categories in updates.items():
            entity_registry.async_update_entity(entity_id, categories=categories)
