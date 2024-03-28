"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.util.ulid import ulid

from ....const import DOMAIN
from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookService):
    """Home Assistant Repairs service to create your own issues."""

    domain = REPAIRS_DOMAIN
    service = "create"
    schema = {
        vol.Required("title"): cv.string,
        vol.Required("description"): cv.string,
        vol.Optional("issue_id", default=ulid): cv.string,
        vol.Optional("domain", default=DOMAIN): cv.string,
        vol.Optional("severity", default=ir.IssueSeverity.WARNING): vol.Coerce(
            ir.IssueSeverity,
        ),
        vol.Optional("persistent", default=False): cv.boolean,
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        ir.async_create_issue(
            self.hass,
            domain=DOMAIN,
            is_fixable=True,
            is_persistent=call.data["persistent"],
            issue_domain=call.data["domain"],
            issue_id=f"user_{call.data['issue_id']}",
            severity=call.data["severity"],
            translation_key="user_issue",
            translation_placeholders={
                "title": call.data["title"],
                "description": call.data["description"],
            },
        )
