"""Spook - Not your homey."""
from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.service import _load_services_file, async_set_service_schema
from homeassistant.loader import async_get_integration

from ..const import DOMAIN
from ..models import AbstractSpookService


@dataclass
class SpookServiceManager:
    """Class to manage Spook services."""

    hass: HomeAssistant

    _services: set[AbstractSpookService] = field(default_factory=set)
    _service_schemas: dict[str, Any] = field(default_factory=dict)

    async def async_setup(self, entry: ConfigEntry) -> None:
        """Set up the Spook services."""
        entry.async_on_unload(self.async_on_unload)
        integration = await async_get_integration(self.hass, DOMAIN)
        self._service_schemas = await self.hass.async_add_executor_job(  # type: ignore
            _load_services_file, self.hass, integration
        )

        # Load all services
        for module_file in Path(__file__).parent.rglob("*.py"):
            if module_file.name == "__init__.py":
                continue
            module = importlib.import_module(f".{module_file.name[:-3]}", __package__)
            service = module.SpookService(self.hass)

            # Only register the service if the domain is the spook integration
            # or if the target integration is loaded.
            if (
                service.domain == DOMAIN
                or service.domain in self.hass.config.components
            ):
                await self.async_register_service(module.SpookService(self.hass))

    async def async_register_service(self, service: AbstractSpookService) -> None:
        """Register a Spook service."""
        service.async_register()
        self._services.add(service)

        # Override service description with Spook's if the service is not
        # for the Spook integration.
        if service.domain != DOMAIN and (
            service_schema := self._service_schemas.get(
                f"{service.domain}_{service.service}"
            )
        ):
            async_set_service_schema(
                self.hass,
                domain=service.domain,
                service=service.service,
                schema=service_schema,
            )

    @callback
    def async_on_unload(self) -> None:
        """Tear down the Spook services."""
        for service in self._services:
            service.async_unregister()
