"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import DISCOVERY_SOURCES, SOURCE_IMPORT
from homeassistant.const import CONF_OPTIONS
from homeassistant.core import CoreState, callback
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers.trigger import Trigger

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

_TRIGGER_SCHEMA = vol.Schema({vol.Optional(CONF_OPTIONS, default=dict): {}})

# Found, rather than asked for. An import is a YAML configuration being moved
# into the interface, and nobody discovered anything by it.
_FOUND = DISCOVERY_SOURCES - {SOURCE_IMPORT}


def _what_it_is(flow: dict[str, Any]) -> tuple[str, str]:
    """Return what tells this discovery apart from another one.

    The unique ID where the integration gave one, which is the device itself.
    One found again gets a new flow, but the same unique ID. Without one there
    is nothing to know the device by, and each discovery is its own.
    """
    context = flow.get("context") or {}
    return flow["handler"], context.get("unique_id") or flow["flow_id"]


class SpookTrigger(Trigger):
    """Spook trigger that fires when Home Assistant discovers something new.

    Core announces a discovery to the frontend with an event that carries no
    data at all, a nudge to go and look. What was found is only in the flows
    in progress, and Home Assistant tells whoever subscribes when one of
    those is started, which is what this follows.

    A device that was found and never set up is found again after every
    restart. Whatever turns up while Home Assistant starts is noted and not
    reported, and each device is reported once for as long as the
    automation is loaded.
    """

    trigger = "device_discovered"

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,  # noqa: ARG003
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config."""
        return _TRIGGER_SCHEMA(config)  # type: ignore[no-any-return]

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        flows = self._hass.config_entries.flow

        # What is on the discovered list already was found before this
        # automation was loaded, and is not news to it.
        seen = {
            _what_it_is(flow)
            for flow in flows.async_progress()
            if flow["context"].get("source") in _FOUND
        }

        @callback
        def flow_changed(change: str, flow_id: str) -> None:
            """Fire for a discovery not seen before."""
            if change != "added":
                return

            try:
                flow = flows.async_get(flow_id)
            except UnknownFlow:
                return

            context = flow.get("context") or {}
            if (source := context.get("source")) not in _FOUND:
                return

            if (found := _what_it_is(flow)) in seen:
                return
            seen.add(found)

            # Taken note of, but no news while starting: that is when Home
            # Assistant finds everything that was there before the restart.
            # `is_running` is not the question, as it is already true while
            # starting.
            if self._hass.state is not CoreState.running:
                return

            placeholders = dict(context.get("title_placeholders") or {})
            name = placeholders.get("name")
            run_action(
                {
                    "flow_id": flow_id,
                    "domain": flow["handler"],
                    "source": source,
                    "name": name,
                    "unique_id": context.get("unique_id"),
                    "title_placeholders": placeholders,
                },
                f"{name or flow['handler']} discovered",
            )

        return flows.async_subscribe_flow(flow_changed)
