"""Spook - Not your homey."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import final

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.service import async_register_admin_service


class AbstractSpookService(ABC):
    """Abstract class to hold a Spook service."""

    hass: HomeAssistant
    domain: str
    service: str
    schema: vol.Schema | None = None
    admin: bool = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the service."""
        self.hass = hass

    @final
    @callback
    def async_register(self) -> None:
        """Register the service with Home Assistant."""
        if self.admin:
            return async_register_admin_service(
                hass=self.hass,
                domain=self.domain,
                service=self.service,
                service_func=self.async_handle_service,
                schema=self.schema,
            )

        self.hass.services.async_register(
            domain=self.domain,
            service=self.service,
            service_func=self.async_handle_service,
            schema=self.schema,
        )

    @final
    @callback
    def async_unregister(self) -> None:
        """Unregister the service from Home Assistant."""
        self.hass.services.async_remove(self.domain, self.service)

    @abstractmethod
    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        raise NotImplementedError
