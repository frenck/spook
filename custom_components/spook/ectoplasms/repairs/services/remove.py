"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.helpers import config_validation as cv, issue_registry as ir

from ....const import DOMAIN
from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookService):
    """Home Assistant Repairs service to create your own issues."""

    domain = REPAIRS_DOMAIN
    service = "remove"
    schema = {vol.Required("issue_id"): cv.string}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        ir.async_delete_issue(self.hass, DOMAIN, f"user_{call.data['issue_id']}")
