"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.zone import (
    DOMAIN,
    ENTITY_ID_HOME,
    UPDATE_FIELDS,
    Zone,
    ZoneStorageCollection,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import DOMAIN as SPOOK_DOMAIN
from ....errors import entity_not_found
from ....helper_collections import async_get_storage_collection
from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


def _is_the_house(entity: Zone) -> bool:
    """Tell whether a zone is the home zone drawn from the house's location.

    Home Assistant only draws it when no zone has taken `zone.home` already:
    zones from YAML and storage are set up first, and one named Home gets that
    entity ID. Those are ordinary zones, and moving the house would not move
    them. The drawn one is the only editable zone without a stored ID.
    """
    return (
        entity.entity_id == ENTITY_ID_HOME
        and entity.editable
        # pylint: disable-next=protected-access
        and "id" not in entity._config  # noqa: SLF001
    )


class SpookService(AbstractSpookAdminService):
    """Zone service to update a zone on the fly, the home zone included."""

    domain = DOMAIN
    service = "update"
    schema = {
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
    } | UPDATE_FIELDS

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_component: EntityComponent[Zone] = self.hass.data[DATA_INSTANCES][DOMAIN]

        collection: ZoneStorageCollection = async_get_storage_collection(
            self.hass, DOMAIN
        )

        if not (entity := entity_component.get_entity(call.data["entity_id"])):
            raise entity_not_found(call.data["entity_id"])

        if _is_the_house(entity):
            await self._async_update_home(call)
            return

        # pylint: disable-next=protected-access
        if not entity.editable or "id" not in entity._config:  # noqa: SLF001
            raise HomeAssistantError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="zone_not_editable",
                translation_placeholders={
                    "entity_id": call.data["entity_id"],
                },
            )

        data = call.data.copy()
        data.pop("entity_id")

        # pylint: disable-next=protected-access
        await collection.async_update_item(entity._config["id"], data)  # noqa: SLF001

    async def _async_update_home(self, call: ServiceCall) -> None:
        """Move or resize the home zone.

        It is not a stored zone: Home Assistant draws it from the location
        set for the whole house, and redraws it when that changes. So this
        changes the location, the same way Home Assistant's own
        `homeassistant.set_location` does, and the radius along with it.

        Only those. Its name is the name of the whole house, and a home zone
        is never passive.
        """
        data = dict(call.data)
        data.pop("entity_id")

        if unsupported := set(data) - {CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS}:
            raise HomeAssistantError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="home_zone_unsupported",
                translation_placeholders={"fields": ", ".join(sorted(unsupported))},
            )

        # Home Assistant keeps the radius of the house in whole meters, and
        # never below zero. Cutting a fraction off quietly would be a
        # different zone than was asked for, and the location is stored
        # without going through the checks its configuration normally does.
        if CONF_RADIUS in data:
            radius = data[CONF_RADIUS]
            if radius != int(radius) or radius < 0:
                raise HomeAssistantError(
                    translation_domain=SPOOK_DOMAIN,
                    translation_key="home_zone_radius",
                )
            data[CONF_RADIUS] = int(radius)

        await self.hass.config.async_update(**data)
