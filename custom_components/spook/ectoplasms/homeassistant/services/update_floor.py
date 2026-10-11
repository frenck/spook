"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, floor_registry as fr
from homeassistant.helpers.typing import UNDEFINED

from ....const import DOMAIN as SPOOK_DOMAIN
from ....errors import floor_not_found
from ....services import AbstractSpookAdminService
from ..entity_registry_entries import clean_aliases

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

_UPDATABLE = ("name", "aliases", "icon", "level")


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to update a floor on the fly.

    Home Assistant can edit a floor in the UI, but nothing could do it from an
    automation. Deleting the floor and creating it again takes every area off
    it, which is a lot to lose over an icon.
    """

    domain = DOMAIN
    service = "update_floor"
    schema = {
        vol.Required("floor_id"): cv.string,
        vol.Optional("name"): cv.string,
        # Aliases replace what the floor has, like the UI does. An empty list
        # clears them.
        vol.Optional("aliases"): vol.All(cv.ensure_list, [cv.string]),
        # `None` clears these, which is why they are not plain validators.
        vol.Optional("icon"): vol.Any(None, cv.icon),
        vol.Optional("level"): vol.Any(None, vol.Coerce(int)),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        floor_id = call.data["floor_id"]
        floor_registry = fr.async_get(self.hass)
        if not floor_registry.async_get_floor(floor_id):
            raise floor_not_found(floor_id)

        # Left out means keep, `None` means clear. Passing everything through
        # would turn an unmentioned icon into "remove the icon".
        changes = {
            field: call.data[field] for field in _UPDATABLE if field in call.data
        }

        if not changes:
            raise HomeAssistantError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="floor_nothing_to_update",
                translation_placeholders={
                    "floor_id": floor_id,
                    "fields": ", ".join(_UPDATABLE),
                },
            )

        # Checked here rather than caught from the registry, which raises a
        # bare ValueError for it. Names match ignoring case and spaces, so a
        # floor can still be renamed to a different spelling of its own name.
        if "name" in changes:
            other = floor_registry.async_get_floor_by_name(changes["name"])
            if other is not None and other.floor_id != floor_id:
                raise HomeAssistantError(
                    translation_domain=SPOOK_DOMAIN,
                    translation_key="floor_name_taken",
                    translation_placeholders={
                        "name": changes["name"],
                        "floor_id": other.floor_id,
                    },
                )

        # Trimmed, and the empty ones dropped, like core does for the UI. An
        # alias of only spaces is one nobody can say or remove from the UI.
        if "aliases" in changes:
            changes["aliases"] = set(clean_aliases(changes["aliases"]))

        floor_registry.async_update(
            floor_id,
            **{field: changes.get(field, UNDEFINED) for field in _UPDATABLE},
        )
