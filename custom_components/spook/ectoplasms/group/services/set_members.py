"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.group import DOMAIN
from homeassistant.helpers import config_validation as cv

from ....group_members import (
    async_check_joining,
    async_entry_of,
    async_write_members,
    identity_of,
)
from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_GROUP = "group"
CONF_MEMBERS = "members"


class SpookService(AbstractSpookAdminService):
    """Group service that replaces a group's members while it is running."""

    domain = DOMAIN
    service = "set_members"
    schema = {
        vol.Required(CONF_GROUP): cv.entity_id,
        vol.Required(CONF_MEMBERS): vol.All(cv.entity_ids_or_uuids, vol.Length(min=1)),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entry = async_entry_of(self.hass, call.data[CONF_GROUP])
        async_check_joining(self.hass, entry, call.data[CONF_MEMBERS])

        # Repeats are dropped rather than refused: the same entity named
        # twice is one member. By identity rather than by the string, because
        # an entity ID and the registry ID of the same entity are two names
        # for one member, and the first name given is the one kept.
        kept: list[str] = []
        seen: set[str] = set()
        for member in call.data[CONF_MEMBERS]:
            if (identity := identity_of(self.hass, member)) in seen:
                continue
            seen.add(identity)
            kept.append(member)

        await async_write_members(self.hass, entry, kept)
