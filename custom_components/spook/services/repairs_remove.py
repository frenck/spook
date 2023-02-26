"""Spook - Not your homie."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.util.ulid import ulid

from . import AbstractSpookService
from ..const import DOMAIN


class SpookService(AbstractSpookService):
    """Home Assistant Repairs service to create your own issues."""

    domain = REPAIRS_DOMAIN
    service = "remove"
    schema = {vol.Required("issue_id"): cv.string}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        ir.async_delete_issue(self.hass, DOMAIN, f"user_{call.data['issue_id']}")
