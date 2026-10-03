"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import automation
from homeassistant.const import EVENT_STATE_CHANGED, STATE_OFF, STATE_ON
from homeassistant.core import callback

from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import Event


class AbstractSpookAutomationReferencesRepair(
    AbstractSpookEntityComponentUnknownReferencesRepair
):
    """Base for the repairs that look for unknown references in automations.

    An automation somebody turned off is left alone. It does nothing while it
    is off, so nothing in it can go wrong yet, and it was often turned off
    exactly because something in it is broken: being told about that again
    and again is noise. The moment it is turned back on is the moment it
    matters, so that is when it is looked at again. #1725.
    """

    def _should_inspect_entity(self, entity: Any) -> bool:
        """Look only at automations that are on.

        One that failed to load is not off, it is broken, and some of these
        repairs exist to say exactly why. That is not somebody's choice to
        leave it alone, so it is still looked at.
        """
        if not isinstance(entity, automation.AutomationEntity):
            return True
        return bool(entity.is_on)

    async def async_activate(self) -> None:
        """Look again whenever an automation is turned on or off.

        Turned on, it is reported straight away rather than at the next look.
        Turned off, what was reported for it is cleared then too.
        """
        await super().async_activate()

        @callback
        def _turned_on_or_off(event_data: Mapping[str, Any]) -> bool:
            """Return whether an automation went from off to on, or back."""
            if not event_data["entity_id"].startswith(f"{automation.DOMAIN}."):
                return False
            if (old := event_data["old_state"]) is None or (
                new := event_data["new_state"]
            ) is None:
                return False
            # Every run updates an automation's attributes, and those are not
            # a reason to look; only the switch between on and off is.
            return {old.state, new.state} == {STATE_ON, STATE_OFF}

        async def _look_again(_: Event) -> None:
            await self.inspect_debouncer.async_call()

        self._event_subs.add(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED, _look_again, event_filter=_turned_on_or_off
            )
        )
