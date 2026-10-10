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
    """Home Assistant Repairs service for unignoring all issues."""

    domain = DOMAIN
    service = "unignore_all"

    schema = {
        # Left out, every issue. Named, only the issues those integrations
        # raised: HACS nagging for a restart after every update, for example,
        # without taking anything else down with it. Named, it has to name
        # something: an empty list from a template that found nothing must
        # not turn into every issue there is.
        vol.Optional("domain"): vol.All(cv.ensure_list, [cv.string], vol.Length(min=1)),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        domains = set(call.data.get("domain", []))
        issue_registry = ir.async_get(self.hass)
        for domain, issue_id in issue_registry.issues:
            if domains and domain not in domains:
                continue
            issue_registry.async_ignore(domain, issue_id, ignore=False)
