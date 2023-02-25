"""Spook - Not your homie."""
from __future__ import annotations

import random

import voluptuous as vol

from homeassistant.components.select import DOMAIN, SelectEntity
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv

from . import AbstractSpookEntityComponentService


class SpookService(AbstractSpookEntityComponentService):
    """Select entity service, select a random option."""

    domain = DOMAIN
    service = "random"
    schema = {vol.Optional("options"): [cv.string]}

    async def async_handle_service(
        self, entity: SelectEntity, call: ServiceCall
    ) -> None:
        """Handle the service call."""
        option = random.choice(call.data.get("options", entity.options))
        if option not in entity.options:
            raise ValueError(f"Option {option} not valid for {entity.entity_id}")
        await entity.async_select_option(option)
