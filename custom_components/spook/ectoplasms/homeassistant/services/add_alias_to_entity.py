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
    """Home Assistant service to add aliases to an entity.

    New aliases go at the end, in the order given, and one it already has is
    not added twice. Whether the entity's own name counts as an alias stays
    as it was.
    """

    domain = DOMAIN
    service = "add_alias_to_entity"
    schema = {
        vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("alias"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)
        new_aliases = clean_aliases(call.data["alias"])

        for entry in async_get_registry_entries(self.hass, call.data["entity_id"]):
            aliases = list(entry.aliases)
            aliases.extend(alias for alias in new_aliases if alias not in aliases)
            entity_registry.async_update_entity(entry.entity_id, aliases=aliases)
