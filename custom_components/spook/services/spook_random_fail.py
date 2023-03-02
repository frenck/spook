"""Spook - Not your homie."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError

from ..const import DOMAIN
from . import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookService):
    """Spook service to randomly fail a service call."""

    domain = DOMAIN
    service = "random_fail"

    async def async_handle_service(self, _: ServiceCall) -> None:
        """Handle the service call."""
        if random.choice([True, False]):
            msg = "Spooked!"
            raise HomeAssistantError(msg)
