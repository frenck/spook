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
    members_of,
)
from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_GROUP = "group"
CONF_MEMBERS = "members"


class SpookService(AbstractSpookAdminService):
    """Group service that adds members to a group while it is running."""

    domain = DOMAIN
    service = "add_members"
    schema = {
        vol.Required(CONF_GROUP): cv.entity_id,
        vol.Required(CONF_MEMBERS): vol.All(cv.entity_ids_or_uuids, vol.Length(min=1)),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entry = async_entry_of(self.hass, call.data[CONF_GROUP])
        async_check_joining(self.hass, entry, call.data[CONF_MEMBERS])

        current = members_of(entry)
        # Appended rather than merged, so the order somebody arranged their
        # group in survives. A member already in it is left where it is.
        joining = [
            member for member in call.data[CONF_MEMBERS] if member not in current
        ]

        await async_write_members(self.hass, entry, current + joining)
