"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.blueprint import DOMAIN
from homeassistant.components.blueprint.errors import FileAlreadyExists
from homeassistant.components.blueprint.importer import fetch_blueprint_from_url
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.components.blueprint.models import DomainBlueprints
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Blueprint integration service to import an Blueprint from an URL."""

    domain = DOMAIN
    service = "import"
    schema = {vol.Required("url"): cv.url}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        try:
            async with async_timeout.timeout(10):
                imported_blueprint = await fetch_blueprint_from_url(
                    self.hass,
                    call.data["url"],
                )
        except (TimeoutError, aiohttp.ClientError) as err:
            msg = "Error fetching blueprint from URL"
            raise HomeAssistantError(msg) from err

        if imported_blueprint is None:
            msg = "This url is not supported"
            raise HomeAssistantError(msg)

        domain_blueprints: dict[str, DomainBlueprints] = self.hass.data.get(DOMAIN, {})
        if imported_blueprint.blueprint.domain not in domain_blueprints:
            msg = f"Unsupported domain: {imported_blueprint.blueprint.domain}"
            raise HomeAssistantError(msg)

        imported_blueprint.blueprint.update_metadata(source_url=call.data["url"])

        try:
            await domain_blueprints[
                imported_blueprint.blueprint.domain
            ].async_add_blueprint(
                imported_blueprint.blueprint,
                imported_blueprint.suggested_filename,
            )
        except FileAlreadyExists as ex:
            msg = "File already exists"
            raise HomeAssistantError(msg) from ex
        except OSError as err:
            msg = "Error writing file"
            raise HomeAssistantError(msg) from err
