"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.repairs import DOMAIN
from homeassistant.helpers import config_validation as cv, issue_registry as ir

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Repairs service for ignoring all issues."""

    domain = DOMAIN
    service = "ignore_all"

    schema = {
        # Left out, every issue. Named, only the issues those integrations
        # raised: HACS nagging for a restart after every update, for example,
        # without taking anything else down with it.
        vol.Optional("domain"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        domains = set(call.data.get("domain", []))
        issue_registry = ir.async_get(self.hass)
        for domain, issue_id in issue_registry.issues:
            if domains and domain not in domains:
                continue
            issue_registry.async_ignore(domain, issue_id, ignore=True)
