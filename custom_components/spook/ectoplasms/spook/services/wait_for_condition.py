"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import CONF_CONDITION, CONF_TIMEOUT
from homeassistant.core import SupportsResponse
from homeassistant.helpers import config_validation as cv

from ....condition_watching import async_condition_watcher, async_validate_condition
from ....const import DOMAIN
from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall, ServiceResponse


class SpookService(AbstractSpookService):
    """Spook action that waits until a condition is true.

    Home Assistant can wait for a template to turn true, and it can wait for a
    trigger. It cannot wait for a condition, so anything you can express with
    the condition building blocks has to be rewritten as a template to be
    waited on.

    Returns straight away when the condition is already true, which is the
    part that makes `wait_for_trigger` awkward for this: that one always waits
    for something to happen, so people write an `if` around it to cover the
    case where it already has.
    """

    domain = DOMAIN
    service = "wait_for_condition"
    supports_response = SupportsResponse.OPTIONAL
    schema = {
        vol.Required(CONF_CONDITION): dict,
        vol.Optional(CONF_TIMEOUT): cv.positive_time_period,
    }

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Wait for the condition, and say whether it arrived."""
        condition_config = await async_validate_condition(
            self.hass, call.data[CONF_CONDITION]
        )

        met = self.hass.loop.create_future()

        def condition_met() -> None:
            """Let the wait finish."""
            if not met.done():
                met.set_result(True)

        watcher = await async_condition_watcher(
            self.hass, condition_config, condition_met
        )
        stop = watcher.async_start()

        # Already true is not something to wait for. Checked after starting so
        # there is no gap where the condition could turn true unnoticed.
        if watcher.met:
            stop()
            return {"completed": True}

        timeout = call.data.get(CONF_TIMEOUT)
        try:
            async with asyncio.timeout(timeout.total_seconds() if timeout else None):
                await met
        except TimeoutError:
            return {"completed": False}
        finally:
            stop()

        return {"completed": True}
