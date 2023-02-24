"""Spook - Not your homey."""
from __future__ import annotations

import random

from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from ..const import DOMAIN
from ..models import AbstractSpookService


class SpookService(AbstractSpookService):
    """Spook service to randomly fail a service call."""

    domain = DOMAIN
    service = "random_fail"

    async def async_handle_service(self, _: ServiceCall) -> None:
        """Handle the service call."""
        if random.choice([True, False]):
            raise HomeAssistantError("Spooked!")
