"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.person import DOMAIN, Person, PersonStorageCollection
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall
    from homeassistant.helpers.entity_component import EntityComponent


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to add a device tracker to a person."""

    domain = DOMAIN
    service = "add_device_tracker"
    schema = {
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
        vol.Required("device_tracker"): vol.All(
            cv.ensure_list,
            [cv.entity_domain("device_tracker")],
        ),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        collection: PersonStorageCollection
        entity_component: EntityComponent[Person]
        _, collection, entity_component = self.hass.data[DOMAIN]

        if not (entity := entity_component.get_entity(call.data["entity_id"])):
            message = f"Could not find entity_id: {call.data['entity_id']}"
            raise HomeAssistantError(message)

        # pylint: disable-next=protected-access
        if not entity.editable or "id" not in entity._config:  # noqa: SLF001
            message = f"This person is not editable: {call.data['entity_id']}"
            raise HomeAssistantError(message)

        await collection.async_update_item(
            # pylint: disable-next=protected-access
            entity._config["id"],  # noqa: SLF001
            {
                "device_trackers": list(
                    set(entity.device_trackers + call.data["device_tracker"]),
                ),
            },
        )
