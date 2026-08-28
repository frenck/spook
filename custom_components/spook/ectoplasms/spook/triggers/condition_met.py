"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_CONDITION, CONF_OPTIONS
from homeassistant.helpers.trigger import Trigger

from ....condition_watching import async_condition_watcher, async_validate_condition

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant
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
                    vol.Required(CONF_CONDITION): dict,
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

        def condition_met() -> None:
            """Run the action, now that the condition has turned true."""
            run_action({}, "condition turned true")

        watcher = await async_condition_watcher(
            self._hass, self._condition, condition_met
        )
        return watcher.async_start()
