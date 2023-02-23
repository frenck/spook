"""Spook - Not your homey."""
import random

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.backports.enum import StrEnum

from ..const import DOMAIN


class SpookServices(StrEnum):
    """Spook services."""

    RANDOM_FAIL = "random_fail"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Spook services."""

    async def _async_random_fail(_: ServiceCall) -> None:
        """Randomly let this service call fail."""
        if random.choice([True, False]):
            raise HomeAssistantError("Spooked!")

    hass.services.async_register(
        DOMAIN,
        SpookServices.RANDOM_FAIL,
        _async_random_fail,
    )
