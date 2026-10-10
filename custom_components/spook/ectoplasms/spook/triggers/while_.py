"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_CONDITION, CONF_OPTIONS
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.trigger import Trigger

from ....condition_watching import async_condition_watcher, async_validate_condition

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.event import EventStateChangedData
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

CONF_EVERY = "every"

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_CONDITION): vol.Any(dict, list, str),
            vol.Required(CONF_EVERY): cv.positive_time_period,
        },
    }
)


class SpookTrigger(Trigger):
    """Spook trigger that keeps firing for as long as a condition holds.

    The nagging trigger. The garage is open, and you want to hear about it
    again in ten minutes, and ten minutes after that, until somebody closes
    it. Home Assistant can do that inside a script with a `repeat` and a
    `delay`, but that holds a run open for as long as the garage is open, so
    the automation's mode has to allow for it and a reload ends it.

    As a trigger it holds nothing open. It fires the moment the condition
    arrives, keeps firing on the interval while it holds, and stops when it
    stops holding.
    """

    trigger = "while"

    _condition: ConfigType
    _every: timedelta

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config, condition and all."""
        shaped: ConfigType = _TRIGGER_SCHEMA(config)
        options = shaped[CONF_OPTIONS]

        if options[CONF_EVERY].total_seconds() <= 0:
            msg = (
                "A repeat interval of zero would fire as fast as Home "
                "Assistant can run it, for as long as the condition holds."
            )
            raise vol.Invalid(msg)

        options[CONF_CONDITION] = await async_validate_condition(
            hass, options[CONF_CONDITION]
        )
        return shaped

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        options: dict[str, Any] = config.options or {}
        self._condition = options[CONF_CONDITION]
        self._every = options[CONF_EVERY]

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        unsub_repeat: CALLBACK_TYPE | None = None
        times = 0

        @callback
        def fire(event: Event[EventStateChangedData] | None) -> None:
            """Run the action, saying how many times it has now run."""
            nonlocal times
            times += 1

            to_state = event.data["new_state"] if event else None
            entity_id = event.data["entity_id"] if event else None
            # Lifted out of the change that turned the condition true, so
            # `trigger.to_state` and friends mean here what they mean
            # everywhere else, and so a condition asking who is behind the run
            # finds the person there. Named one by one rather than merged: what
            # is handed to `run_action` overrides the automation's own
            # `trigger.id` and `platform`.
            carried = (
                {"from_state": event.data["old_state"], "to_state": to_state}
                if event
                else {}
            )

            run_action(
                {
                    "entity_id": entity_id,
                    **carried,
                    "times": times,
                    "every": self._every,
                },
                f"a condition held, run {times}",
                to_state.context if to_state else None,
            )

        @callback
        def stop_repeating() -> None:
            """Drop the interval, if one is running."""
            nonlocal unsub_repeat, times
            if unsub_repeat is not None:
                unsub_repeat()
                unsub_repeat = None
            times = 0

        @callback
        def repeat(_now: datetime) -> None:
            """Fire again, the condition still holding."""
            fire(None)

        @callback
        def condition_turned(
            *,
            met: bool,
            event: Event[EventStateChangedData] | None,
        ) -> None:
            """Start or stop repeating, depending on which way it turned."""
            nonlocal unsub_repeat

            if not met:
                stop_repeating()
                return

            fire(event)
            unsub_repeat = async_track_time_interval(
                self._hass,
                repeat,
                self._every,
                # Nothing should still be nagging while Home Assistant is
                # shutting down, and a timer that outlives the run it belongs
                # to is a leak whether anyone notices or not.
                cancel_on_shutdown=True,
            )

        watcher = await async_condition_watcher(
            self._hass, self._condition, condition_turned
        )
        stop_watching = watcher.async_start()

        @callback
        def stop() -> None:
            """Stop watching, and stop repeating."""
            stop_watching()
            stop_repeating()

        return stop
