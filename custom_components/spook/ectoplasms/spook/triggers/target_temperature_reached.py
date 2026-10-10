"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS, CONF_TARGET
from homeassistant.core import callback
from homeassistant.helpers.target import TargetSelection
from homeassistant.helpers.trigger import Trigger

from ....target_watching import StateChangeWatcher, watchable_target
from ....temperature_targets import (
    CONF_TOLERANCE,
    Reading,
    only_climate_and_water_heaters,
    reading,
    validate_tolerance,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.event import EventStateChangedData
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): watchable_target,
        vol.Optional(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_TOLERANCE, default=0.0): validate_tolerance,
        },
    }
)


def _reached(before: Reading, after: Reading, distance: float) -> bool:
    """Tell whether the temperature moving from before to after reached it.

    Getting there counts, and so does jumping past it: a sensor that reports
    in whole degrees, or a room that overshoots, can go from below the target
    to above it without ever reporting it.
    """
    if before.at_target(distance):
        return False
    if after.at_target(distance):
        return True
    return (before.current < after.low and after.current > after.high) or (
        before.current > after.high and after.current < after.low
    )


# Everything here is called by the base class or by an event, so there is
# nothing public to count.
# pylint: disable-next=too-few-public-methods
class _TemperatureTracker(StateChangeWatcher):
    """Watch a target's devices for the temperature reaching its target."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        tolerance: float,
        on_reached: Callable[[Event[EventStateChangedData]], None],
    ) -> None:
        """Initialize the tracker."""
        super().__init__(
            hass, target_selection, entity_filter=only_climate_and_water_heaters
        )
        self._tolerance = tolerance
        self._on_reached = on_reached

    @callback
    def _entity_changed(self, event: Event[EventStateChangedData]) -> None:
        """Compare where the temperature was with where it is now."""
        before = reading(event.data["old_state"])
        after = reading(event.data["new_state"])

        # Without a reading on both sides there is no movement to judge: a
        # device coming back, or switched on, did not just get somewhere.
        if before is None or after is None:
            return

        # A new setpoint is somebody moving the target, not the temperature
        # getting to it. Set onto the temperature it already is, nothing was
        # reached; the next move is judged against the new target.
        if not before.same_target(after):
            return

        if _reached(before, after, self._tolerance):
            self._on_reached(event)


class SpookTrigger(Trigger):
    """Spook trigger that fires when a temperature reaches its target.

    A thermostat or water heater knows where it is heading and where it is.
    Home Assistant can tell you when either one changes, but not when the one
    arrives at the other, which is the moment that matters: the bathroom is
    warm, the water is hot.
    """

    trigger = "target_temperature_reached"

    _target: ConfigType
    _tolerance: float

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,  # noqa: ARG003
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config."""
        return _TRIGGER_SCHEMA(config)  # type: ignore[no-any-return]

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        options: dict[str, Any] = config.options or {}
        self._tolerance = options.get(CONF_TOLERANCE, 0.0)
        self._target = config.target or {}

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def target_reached(event: Event[EventStateChangedData]) -> None:
            """Run the action for the device that got there."""
            entity_id = event.data["entity_id"]
            to_state = event.data["new_state"]
            payload: dict[str, Any] = {
                "entity_id": entity_id,
                "from_state": event.data["old_state"],
                "to_state": to_state,
                "tolerance": self._tolerance,
            }
            run_action(
                payload,
                f"{entity_id} reached its target temperature",
                to_state.context if to_state else None,
            )

        tracker = _TemperatureTracker(
            self._hass, TargetSelection(self._target), self._tolerance, target_reached
        )
        return await tracker.async_setup()
