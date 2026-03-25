"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.input_number import (
    CONF_INITIAL,
    CONF_MAX,
    CONF_MIN,
    CONF_STEP,
    DOMAIN,
    MODE_BOX,
    MODE_SLIDER,
    NumberStorageCollection,
    _cv_input_number,
)
from homeassistant.const import CONF_ICON, CONF_ID, CONF_MODE, CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_INPUT_NUMBER_ID = "input_number_id"

CREATE_FIELDS = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_INPUT_NUMBER_ID): cv.slug,
    vol.Optional(CONF_MIN, default=0): vol.Coerce(float),
    vol.Optional(CONF_MAX, default=100): vol.Coerce(float),
    vol.Optional(CONF_INITIAL): vol.Coerce(float),
    vol.Optional(CONF_STEP, default=1): vol.All(vol.Coerce(float), vol.Range(min=1e-9)),
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_MODE, default=MODE_SLIDER): vol.In([MODE_SLIDER, MODE_BOX]),
}


class SpookService(AbstractSpookAdminService):
    """Input number service to create a new helper on the fly."""

    domain = DOMAIN
    service = "create"
    schema = vol.All(vol.Schema(CREATE_FIELDS), _cv_input_number)

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        input_number_id = call.data.get(CONF_INPUT_NUMBER_ID)
        data = {k: v for k, v in call.data.items() if k != CONF_INPUT_NUMBER_ID}

        collection: NumberStorageCollection
        if DOMAIN in self.hass.data:
            collection = self.hass.data[DOMAIN]
        else:
            # Major hack to get around edge cases. 👻
            collection = self.hass.data["websocket_api"][
                "input_number/list"
            ][0].__self__.storage_collection

        if input_number_id:
            async with self.hass.data.setdefault(
                f"{DOMAIN}_create_lock", asyncio.Lock()
            ):
                desired_entity_id = f"{DOMAIN}.{input_number_id}"
                ent_reg = er.async_get(self.hass)
                if ent_reg.async_get(desired_entity_id):
                    message = f"An input number with entity ID '{desired_entity_id}' already exists"
                    raise HomeAssistantError(message)

                item = await collection.async_create_item(data)

                # The entity_id is derived from the name by default. Update the
                # entity registry to match the requested input_number_id instead.
                if (
                    current_entity_id := ent_reg.async_get_entity_id(
                        DOMAIN, DOMAIN, item[CONF_ID]
                    )
                ) and current_entity_id != desired_entity_id:
                    ent_reg.async_update_entity(
                        current_entity_id, new_entity_id=desired_entity_id
                    )
        else:
            await collection.async_create_item(data)
