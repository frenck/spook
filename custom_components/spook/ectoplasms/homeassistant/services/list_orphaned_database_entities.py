"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.components.recorder import get_instance
from homeassistant.core import ServiceResponse, SupportsResponse
from homeassistant.helpers.recorder import session_scope

from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

_RECORDED_ENTITY_IDS = text("SELECT DISTINCT(entity_id) FROM states_meta")


def _recorded_entity_ids(hass: HomeAssistant) -> set[str]:
    """Return every entity ID the recorder has ever written down.

    Runs on the recorder's own thread, on the connection it already has.
    Opening a second engine here would put the whole query on the event loop,
    where a large or remote database stalls everything else in the house
    while it reads, and would leave a connection pool behind afterwards.
    """
    with session_scope(hass=hass, read_only=True) as session:
        return {row[0] for row in session.execute(_RECORDED_ENTITY_IDS)}


class SpookService(AbstractSpookService):
    """Home Assistant Core integration service to list all orphaned database entities."""

    domain = DOMAIN
    service = "list_orphaned_database_entities"
    supports_response = SupportsResponse.ONLY

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        recorded = await get_instance(self.hass).async_add_executor_job(
            _recorded_entity_ids, self.hass
        )
        orphaned = recorded.difference(self.hass.states.async_entity_ids())

        if call.return_response:
            return {
                "count": len(orphaned),
                "entities": list(orphaned),
            }
        return None
