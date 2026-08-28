"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_CONDITION, CONF_OPTIONS
from homeassistant.helpers.trigger import Trigger

from ....condition_watching import async_condition_watcher, async_validate_condition

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.event import EventStateChangedData
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType


class SpookTrigger(Trigger):
    """Spook trigger that fires when a condition turns true.

    A condition is true or false, and the moment it goes from one to the other
    is a thing worth reacting to. Home Assistant has a trigger for a template
    turning true and one for a state arriving, but nothing that takes the
    condition building blocks, so anything more involved than a single state
    has to be rewritten as a template.

    Only the turn counts. A condition that is already true when the automation
    loads is not a change, so this does not fire for it, the same as the
    template trigger.
    """

    trigger = "condition_met"

    _condition: ConfigType

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config, condition and all."""
        shaped: ConfigType = vol.Schema(
            {
                vol.Required(CONF_OPTIONS): {
                    # A sequence is what the `condition` selector hands over,
                    # a mapping is what people write by hand.
                    vol.Required(CONF_CONDITION): vol.Any(dict, list, str),
                },
            }
        )(config)
        shaped[CONF_OPTIONS][CONF_CONDITION] = await async_validate_condition(
            hass, shaped[CONF_OPTIONS][CONF_CONDITION]
        )
        return shaped

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        options: dict[str, Any] = config.options or {}
        self._condition = options[CONF_CONDITION]

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        def condition_met(event: Event[EventStateChangedData] | None) -> None:
            """Run the action, now that the condition has turned true.

            Reports the state change that turned it, when a state change did,
            the same shape Home Assistant's template trigger reports. Which is
            what carries the user through: an automation starts a fresh
            context, so a condition asking who is behind the run reads it off
            `to_state`.
            """
            to_state = event.data["new_state"] if event else None
            entity_id = event.data["entity_id"] if event else None

            run_action(
                {
                    "entity_id": entity_id,
                    "from_state": event.data["old_state"] if event else None,
                    "to_state": to_state,
                },
                f"{entity_id} turned the condition true"
                if entity_id
                else "the condition turned true on its own",
                to_state.context if to_state else None,
            )

        watcher = await async_condition_watcher(
            self._hass, self._condition, condition_met
        )
        return watcher.async_start()
