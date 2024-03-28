"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.config_entries import DISCOVERY_SOURCES, SOURCE_IGNORE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.translation import async_get_translations

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to ignore all discovered devices."""

    domain = DOMAIN
    service = "ignore_all_discovered"
    schema = {vol.Optional("domain"): vol.All(cv.ensure_list, [cv.string])}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        flows_to_ignore = [
            flow
            for flow in self.hass.config_entries.flow.async_progress()
            if (
                "context" in flow
                and "source" in flow["context"]
                and flow["context"]["source"] in DISCOVERY_SOURCES
                and (
                    "domain" not in call.data or flow["handler"] in call.data["domain"]
                )
            )
        ]

        translations = await async_get_translations(
            self.hass,
            "en",
            "config_flow",
            integrations=(flow["handler"] for flow in flows_to_ignore),
            config_flow=True,
        )

        tasks = []
        for flow in flows_to_ignore:
            title = "Ignored by Spook"
            if flow_title := translations.get(
                f"component.{flow['handler']}.config.flow_title",
            ):
                title = flow_title.format(**flow["context"]["title_placeholders"])
            elif (
                "title_placeholders" in flow["context"]
                and "name" in flow["context"]["title_placeholders"]
            ):
                title = flow["context"]["title_placeholders"]["name"]

            tasks.append(
                self.hass.config_entries.flow.async_init(
                    flow["handler"],
                    context={"source": SOURCE_IGNORE},
                    data={
                        "unique_id": flow["context"]["unique_id"],
                        "title": f"{title} 👻",
                    },
                ),
            )

        if tasks:
            await asyncio.gather(*tasks)
