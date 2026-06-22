"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import create_engine, text

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.components.recorder import get_instance
from homeassistant.core import ServiceResponse, SupportsResponse

from ....services import AbstractSpookService

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant, ServiceCall


def _list_database_entity_ids(db_url: str) -> list[str]:
    """List entity IDs stored in the recorder database."""
    query = text(
        """
        SELECT DISTINCT(entity_id) FROM states_meta
        """
    )
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            response = conn.execute(query)
            return [entity_id for (entity_id,) in response]
    finally:
        engine.dispose()


async def async_get_orphaned_database_entities(
    hass: HomeAssistant,
) -> set[str]:
    """Return recorder entity IDs that are not in the state machine."""
    db_url = get_instance(hass).db_url
    db_list: Iterable[str] = await hass.async_add_executor_job(
        _list_database_entity_ids, db_url
    )
    return set(db_list).difference(hass.states.async_entity_ids())


class SpookService(AbstractSpookService):
    """Home Assistant Core integration service to list all orphaned database entities."""

    domain = DOMAIN
    service = "list_orphaned_database_entities"
    supports_response = SupportsResponse.ONLY

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        entities = await async_get_orphaned_database_entities(self.hass)
        if call.return_response:
            return {
                "count": len(entities),
                "entities": sorted(entities),
            }
        return None
