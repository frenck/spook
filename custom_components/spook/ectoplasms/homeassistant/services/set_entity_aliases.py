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
    """Home Assistant service to set the aliases of an entity.

    Replaces the aliases written out, and keeps whether the entity's own name
    counts as one, at the front where the UI shows it. Taking the entity's own
    name away is a different choice, and one the UI already offers.
    """

    domain = DOMAIN
    service = "set_entity_aliases"
    schema = {
        vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("aliases"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)
        new_aliases: list[er.AliasEntry] = list(clean_aliases(call.data["aliases"]))

        for entry in async_get_registry_entries(self.hass, call.data["entity_id"]):
            keeps_own_name = er.COMPUTED_NAME in entry.aliases
            aliases = (
                [er.COMPUTED_NAME, *new_aliases] if keeps_own_name else new_aliases
            )
            entity_registry.async_update_entity(entry.entity_id, aliases=aliases)
