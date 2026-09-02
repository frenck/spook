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

        # By identity, not by the string. A group holds either an entity ID or
        # a registry ID, so comparing what was asked for against what is
        # stored has to go through the same resolving, or the same entity
        # arrives twice under its two names.
        held = {identity_of(self.hass, member) for member in current}

        # Appended rather than merged, so the order somebody arranged their
        # group in survives. A member already in it is left where it is, and
        # `held` grows as we go so naming one twice in a single call is the
        # same as naming it once.
        joining: list[str] = []
        for member in call.data[CONF_MEMBERS]:
            if (identity := identity_of(self.hass, member)) in held:
                continue
            held.add(identity)
            joining.append(member)

        await async_write_members(self.hass, entry, current + joining)
