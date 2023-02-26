"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components.repairs import DOMAIN
from homeassistant.core import ServiceCall
from homeassistant.helpers import issue_registry as ir

from . import AbstractSpookService


class SpookService(AbstractSpookService):
    """Home Assistant Repairs service for ignoring all issues."""

    domain = DOMAIN
    service = "ignore_all"

    async def async_handle_service(self, _: ServiceCall) -> None:
        """Handle the service call."""
        issue_registry = ir.async_get(self.hass)
        for domain, issue_id in issue_registry.issues:
            issue_registry.async_ignore(domain, issue_id, True)
