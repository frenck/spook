"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.automation import DOMAIN, BaseAutomationEntity
from homeassistant.const import STATE_ON

from ....services import AbstractSpookEntityComponentService
from ....timed_states import a_stretch_of_time, async_get_timed_states

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_DURATION = "duration"


class SpookService(AbstractSpookEntityComponentService[BaseAutomationEntity]):
    """Automation service that turns one on for a while, not for good.

    The other way round from a snooze, and the same trap: an automation
    turned on stays on, so "just for tonight" needs somebody to remember. The
    usual way round it is a helper entity and a second automation to turn the
    first one back off, which is two moving parts for something that should
    be one.
    """

    domain = DOMAIN
    service = "turn_on_for"
    schema = {vol.Required(CONF_DURATION): a_stretch_of_time}

    async def async_handle_service(
        self,
        entity: BaseAutomationEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        await async_get_timed_states(self.hass).async_hold(
            entity.entity_id,
            call.data[CONF_DURATION],
            STATE_ON,
            # Carried through, so an automation watching this one switch on
            # can still tell who asked for it. Spook's own context conditions
            # read the person off exactly that.
            context=call.context,
        )
