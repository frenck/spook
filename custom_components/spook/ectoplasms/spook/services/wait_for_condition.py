"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import CONF_CONDITION, CONF_TIMEOUT
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ....condition_watching import (
    async_condition_watcher,
    async_validate_condition,
    iter_templates,
)
from ....const import DOMAIN
from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import Event, ServiceCall, ServiceResponse
    from homeassistant.helpers.event import EventStateChangedData
    from homeassistant.helpers.typing import ConfigType


def _reject_rendered_templates(config: ConfigType) -> None:
    """Refuse a condition whose templates were rendered before we got here.

    A script renders every template in the action data before calling the
    action, condition templates included. So `{{ is_state(...) }}` arrives as
    the `True` or `False` it happened to be at that moment, and a
    `numeric_state` value template arrives as a number. The condition still
    validates, still checks, and never turns, so the wait would be a hang.

    A rendered template is one without any Jinja left in it, which is what
    Home Assistant calls static. Nobody writes those on purpose.
    """
    if any(template.is_static for template in iter_templates(config)):
        msg = (
            "The templates in this condition were rendered before this action "
            "ran, so they cannot turn true any more. Use a condition without "
            "templates, or wait on the template itself with 'wait_template'."
        )
        raise ServiceValidationError(msg)


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
        # A sequence is what the `condition` selector hands over, a mapping is
        # what people write by hand.
        vol.Required(CONF_CONDITION): vol.Any(dict, list, str),
        vol.Optional(CONF_TIMEOUT): cv.positive_time_period,
    }

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Wait for the condition, and say whether it arrived."""
        try:
            condition_config = await async_validate_condition(
                self.hass, call.data[CONF_CONDITION]
            )
        except vol.Invalid as err:
            # Bad input from the caller, not a fault in here, and a raw
            # voluptuous error in the log says that far less clearly.
            raise ServiceValidationError(str(err)) from err

        _reject_rendered_templates(condition_config)

        met = self.hass.loop.create_future()

        def condition_met(_event: Event[EventStateChangedData] | None) -> None:
            """Let the wait finish. What turned it does not matter here."""
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

        # A zero timeout is a valid ask: look now, do not wait. Which is why
        # this asks whether a timeout was given rather than whether it is
        # truthy, as `timedelta(0)` is false.
        timeout = call.data.get(CONF_TIMEOUT)
        seconds = None if timeout is None else timeout.total_seconds()

        try:
            async with asyncio.timeout(seconds):
                await met
        except TimeoutError:
            return {"completed": False}
        finally:
            stop()

        return {"completed": True}
