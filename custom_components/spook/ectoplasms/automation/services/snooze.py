"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.automation import DOMAIN, BaseAutomationEntity
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookEntityComponentService
from ....snoozing import async_get_snoozing

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.core import ServiceCall

CONF_DURATION = "duration"


def _a_stretch_of_time(value: Any) -> timedelta:
    """Validate a duration that is actually a duration.

    `cv.positive_time_period` counts nothing at all as positive, and a snooze
    of nothing is an automation turned off and straight back on: a pulse
    through everything watching it, in exchange for no quiet whatsoever.
    """
    period = cv.positive_time_period(value)

    if not period:
        msg = "duration must be longer than nothing"
        raise vol.Invalid(msg)

    return period


class SpookService(AbstractSpookEntityComponentService[BaseAutomationEntity]):
    """Automation service that turns one off for a while, not for good.

    Turning an automation off is the only way to make it stop for an hour,
    and an automation turned off stays off: past the restart, past the
    weekend, until somebody notices. The usual way round it is a helper
    entity and a second automation to turn the first one back on, which is
    two moving parts for something that should be one.
    """

    domain = DOMAIN
    service = "snooze"
    schema = {vol.Required(CONF_DURATION): _a_stretch_of_time}

    async def async_handle_service(
        self,
        entity: BaseAutomationEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        await async_get_snoozing(self.hass).async_snooze(
            entity.entity_id,
            call.data[CONF_DURATION],
            # Carried through, so an automation watching this one switch off
            # can still tell who asked for it. Spook's own context conditions
            # read the person off exactly that.
            context=call.context,
        )
