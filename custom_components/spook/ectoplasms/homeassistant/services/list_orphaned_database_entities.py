"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.db_schema import StatesMeta
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import ServiceResponse, SupportsResponse

from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookService):
    """Home Assistant Core integration service to list all orphaned database entities."""

    domain = DOMAIN
    service = "list_orphaned_database_entities"
    supports_response = SupportsResponse.ONLY

    def _fetch_recorded_entities(self) -> list[str]:
        """Return all entity IDs known to the recorder database.

        Runs in the recorder's executor thread; the database access here is
        synchronous and must never touch the event loop.
        """
        with session_scope(hass=self.hass, read_only=True) as session:
            return [
                entity_id
                for (entity_id,) in session.execute(select(StatesMeta.entity_id))
            ]

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        recorder = get_instance(self.hass)
        db_list = await recorder.async_add_executor_job(
            self._fetch_recorded_entities,
        )
        states_list = self.hass.states.async_entity_ids()
        orphaned = set(db_list).difference(states_list)
        if call.return_response:
            return {
                "count": len(orphaned),
                "entities": sorted(orphaned),
            }
        return None
