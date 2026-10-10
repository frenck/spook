"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.homeassistant import DOMAIN

from ....services import AbstractSpookAdminService
from . import CONFIG_ENTRY_SERVICE_SCHEMA, async_config_entry_ids

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to enable a config entry."""

    domain = DOMAIN
    service = "enable_config_entry"
    schema = CONFIG_ENTRY_SERVICE_SCHEMA

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        for config_entry_id in async_config_entry_ids(self.hass, call):
            await self.hass.config_entries.async_set_disabled_by(
                config_entry_id,
                disabled_by=None,
            )
