"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    floor_registry as fr,
)
from homeassistant.helpers.typing import UNDEFINED

from ....const import DOMAIN as SPOOK_DOMAIN
from ....errors import area_not_found, entity_not_found, floor_not_found
from ....services import AbstractSpookAdminService
from ..labels import async_check_labels_exist

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

_UPDATABLE = (
    "name",
    "aliases",
    "floor_id",
    "icon",
    "picture",
    "labels",
    "temperature_entity_id",
    "humidity_entity_id",
)


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to update an area on the fly.

    Home Assistant can edit an area in the UI, but nothing could do it from an
    automation. Deleting the area and creating it again takes every device and
    entity out of it, which is a lot to lose over an icon.
    """

    domain = DOMAIN
    service = "update_area"
    schema = {
        vol.Required("area_id"): cv.string,
        vol.Optional("name"): cv.string,
        # Aliases and labels replace what the area has, like the UI does.
        # An empty list clears them.
        vol.Optional("aliases"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("labels"): vol.All(cv.ensure_list, [cv.string]),
        # `None` clears these, which is why they are not plain validators.
        vol.Optional("floor_id"): vol.Any(None, cv.string),
        vol.Optional("icon"): vol.Any(None, cv.icon),
        vol.Optional("picture"): vol.Any(None, cv.string),
        vol.Optional("temperature_entity_id"): vol.Any(None, cv.entity_id),
        vol.Optional("humidity_entity_id"): vol.Any(None, cv.entity_id),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        area_id = call.data["area_id"]
        area_registry = ar.async_get(self.hass)
        if not area_registry.async_get_area(area_id):
            raise area_not_found(area_id)

        # Left out means keep, `None` means clear. Passing everything through
        # would turn an unmentioned icon into "remove the icon".
        changes = {
            field: call.data[field] for field in _UPDATABLE if field in call.data
        }

        if not changes:
            raise HomeAssistantError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="area_nothing_to_update",
                translation_placeholders={
                    "area_id": area_id,
                    "fields": ", ".join(_UPDATABLE),
                },
            )

        self._async_check_references(area_id, changes)

        if "aliases" in changes:
            changes["aliases"] = set(changes["aliases"])
        if "labels" in changes:
            changes["labels"] = set(changes["labels"])

        try:
            area_registry.async_update(
                area_id,
                **{field: changes.get(field, UNDEFINED) for field in _UPDATABLE},
            )
        except ValueError as err:
            # The registry refuses a sensor of the wrong kind. Its wording says
            # why, so it is passed on, as something an automation can catch.
            raise HomeAssistantError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="area_cannot_update",
                translation_placeholders={"area_id": area_id, "error": str(err)},
            ) from err

    def _async_check_references(self, area_id: str, changes: dict[str, Any]) -> None:
        """Raise unless the name is free and everything named exists.

        The registry stores a floor or label that does not exist without a
        word, and the area then sits on a floor nobody can find. All of it is
        checked before anything is written, so a refused call changes nothing.
        """
        # Checked here rather than caught from the registry: its error for this
        # is a plain ValueError, the same kind it raises for a wrong sensor.
        # Names match ignoring case and spaces, so an area can still be renamed
        # to a different spelling of its own name.
        if "name" in changes:
            other = ar.async_get(self.hass).async_get_area_by_name(changes["name"])
            if other is not None and other.id != area_id:
                raise HomeAssistantError(
                    translation_domain=SPOOK_DOMAIN,
                    translation_key="area_name_taken",
                    translation_placeholders={
                        "name": changes["name"],
                        "area_id": other.id,
                    },
                )

        floor_id = changes.get("floor_id")
        if floor_id is not None and not fr.async_get(self.hass).async_get_floor(
            floor_id
        ):
            raise floor_not_found(floor_id)

        if "labels" in changes:
            async_check_labels_exist(self.hass, changes["labels"])

        # The registry looks these up in the state machine, so that is where
        # they have to exist.
        for field in ("temperature_entity_id", "humidity_entity_id"):
            entity_id = changes.get(field)
            if entity_id is not None and self.hass.states.get(entity_id) is None:
                raise entity_not_found(entity_id)
