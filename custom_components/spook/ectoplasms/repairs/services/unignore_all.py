"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.repairs import DOMAIN
from homeassistant.helpers import issue_registry as ir

from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookService):
    """Home Assistant Repairs service for unignoring all issues."""

    domain = DOMAIN
    service = "unignore_all"

    async def async_handle_service(self, _: ServiceCall) -> None:
        """Handle the service call."""
        issue_registry = ir.async_get(self.hass)
        for domain, issue_id in issue_registry.issues:
            issue_registry.async_ignore(domain, issue_id, ignore=False)
