"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError

from ....const import DOMAIN
from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookService):
    """Spook service to fail a service call."""

    domain = DOMAIN
    service = "boo"

    async def async_handle_service(self, _: ServiceCall) -> None:
        """Handle the service call."""
        msg = "Spooked!"
        raise HomeAssistantError(msg)
