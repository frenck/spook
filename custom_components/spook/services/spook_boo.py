"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from . import AbstractSpookService
from ..const import DOMAIN


class SpookService(AbstractSpookService):
    """Spook service to fail a service call."""

    domain = DOMAIN
    service = "boo"

    async def async_handle_service(self, _: ServiceCall) -> None:
        """Handle the service call."""
        raise HomeAssistantError("Spooked!")
