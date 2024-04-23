"""Spook - Your homie."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.select import DOMAIN, SelectEntity
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[SelectEntity]):
    """Select entity service, select a random option."""

    domain = DOMAIN
    service = "random"
    schema = {vol.Optional("options"): [cv.string]}

    async def async_handle_service(
        self,
        entity: SelectEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        option = random.choice(call.data.get("options", entity.options))  # noqa: S311
        if option not in entity.options:
            msg = f"Option {option} not valid for {entity.entity_id}"
            raise ValueError(msg)
        await entity.async_select_option(option)
