"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.homeassistant import DOMAIN

from ....services import AbstractSpookAdminService
from . import EXPOSURE_SERVICE_SCHEMA, async_set_voice_assistant_exposure

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to stop exposing an entity."""

    domain = DOMAIN
    service = "unexpose_entity"
    schema = EXPOSURE_SERVICE_SCHEMA

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        async_set_voice_assistant_exposure(self.hass, call, should_expose=False)
