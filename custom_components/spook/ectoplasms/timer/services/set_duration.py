"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.timer import (
  CONF_DURATION,
  DOMAIN,
  Timer,
  TimerStorageCollection,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import DATA_INSTANCES

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
  from homeassistant.core import ServiceCall
  from homeassistant.helpers.entity_component import EntityComponent


class SpookService(AbstractSpookAdminService):
  """Home Assistant service to add a device tracker to a person."""

  domain = DOMAIN
  service = "set_duration"
  schema = {
    vol.Required("entity_id"): cv.entity_domain(DOMAIN),
    vol.Required(CONF_DURATION): cv.time_period,
  }

  async def async_handle_service(self, call: ServiceCall) -> None:
    """Handle the service call."""
    entity_component: [EntityComponent[Timer]] = self.hass.data[DATA_INSTANCES][
      DOMAIN
    ]

    collection: TimerStorageCollection
    if DOMAIN in self.hass.data:
      collection = self.hass.data[DOMAIN]
    else:
      # Major hack borrowed from ../../zone/services/create.py:27  👻
      collection = self.hass.data["websocket_api"]["timer/list"][
        0
      ].__self__.storage_collection

    if not (entity := entity_component.get_entity(call.data["entity_id"])):
      message = f"Could not find entity_id: {call.data['entity_id']}"
      raise HomeAssistantError(message)

    # pylint: disable-next=protected-access
    if not entity.editable or "id" not in entity._config:  # noqa: SLF001
      message = f"This timer is not editable: {call.data['entity_id']}"
      raise HomeAssistantError(message)

    # pylint: disable-next=protected-access
    updates = entity._config.copy()  # noqa: SLF001
    item_id = updates.pop("id")
    updates.update({
      CONF_DURATION: call.data[CONF_DURATION],
    })

    await collection.async_update_item(item_id, updates)
