"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import config_validation as cv, entity_registry as er

from ....services import AbstractSpookAdminService
from ..entity_registry_entries import async_get_registry_entries, clean_aliases

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to remove aliases from an entity.

    Only the aliases named go. Whether the entity's own name counts as an
    alias is not one of them, and stays as it was.
    """

    domain = DOMAIN
    service = "remove_alias_from_entity"
    schema = {
        vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("alias"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)
        removed = set(clean_aliases(call.data["alias"]))

        for entry in async_get_registry_entries(self.hass, call.data["entity_id"]):
            # The entity's own name is kept as a marker, not as text, so it is
            # never among the aliases named here, and never removed.
            aliases = [alias for alias in entry.aliases if alias not in removed]
            entity_registry.async_update_entity(entry.entity_id, aliases=aliases)
