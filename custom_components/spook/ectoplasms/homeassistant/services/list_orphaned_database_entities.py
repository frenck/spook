"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import create_engine, text

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.components.recorder import (
    get_instance,
)
from homeassistant.core import ServiceResponse, SupportsResponse

from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookService):
    """Home Assistant Core integration service to list all orphaned database entities."""

    domain = DOMAIN
    service = "list_orphaned_database_entities"
    supports_response = SupportsResponse.ONLY

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        query = text(
            """
            SELECT DISTINCT(entity_id) FROM states_meta
            """
        )
        db_url = get_instance(self.hass).db_url
        engine = create_engine(db_url)
        with engine.connect() as conn:
            response = conn.execute(query)
            db_list = [e[0] for e in response]
        states_list = self.hass.states.async_entity_ids()
        compared_list = set(db_list).difference(states_list)
        if call.return_response:
            return {
                "count": len(compared_list),
                "entities": list(compared_list),
            }
        return None
