"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.components.recorder import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.services import (
    ATTR_KEEP_DAYS,
    SERVICE_PURGE_ENTITIES,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_RESTORED
from homeassistant.helpers import entity_registry as er

from ....services import AbstractSpookAdminService
from .list_orphaned_database_entities import async_get_orphaned_database_entities

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to delete all orphaned entities."""

    domain = DOMAIN
    service = "delete_all_orphaned_entities"

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        orphaned_database_entities = await async_get_orphaned_database_entities(
            self.hass
        )
        if orphaned_database_entities:
            await self.hass.services.async_call(
                RECORDER_DOMAIN,
                SERVICE_PURGE_ENTITIES,
                {
                    ATTR_ENTITY_ID: sorted(orphaned_database_entities),
                    ATTR_KEEP_DAYS: 0,
                },
                blocking=True,
                context=call.context,
            )

        entity_registry = er.async_get(self.hass)
        for state in self.hass.states.async_all():
            if not state.attributes.get(ATTR_RESTORED):
                continue
            entity_registry.async_remove(state.entity_id)
            self.hass.states.async_remove(state.entity_id, call.context)
