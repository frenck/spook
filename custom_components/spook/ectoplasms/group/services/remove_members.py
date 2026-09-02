"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.group import DOMAIN
from homeassistant.helpers import config_validation as cv

from ....group_members import (
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
    """Group service that takes members out of a group while it is running."""

    domain = DOMAIN
    service = "remove_members"
    schema = {
        vol.Required(CONF_GROUP): cv.entity_id,
        vol.Required(CONF_MEMBERS): vol.All(cv.entity_ids_or_uuids, vol.Length(min=1)),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call.

        Naming something that is not in the group is not an error. This is
        how somebody clears out a member that no longer exists, and asking
        twice should not start failing.
        """
        entry = async_entry_of(self.hass, call.data[CONF_GROUP])
        leaving = set(call.data[CONF_MEMBERS])

        await async_write_members(
            self.hass,
            entry,
            [member for member in members_of(entry) if member not in leaving],
        )
