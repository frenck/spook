"""Spook - Your homie."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
)
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.const import (
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback, split_entity_id
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import Trigger

from ....setpoints import whole_position
from ....target_watching import watchable_target

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State
    from homeassistant.helpers.event import EventStateChangedData
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

_DOMAINS = (COVER_DOMAIN, VALVE_DOMAIN)

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): watchable_target,
        vol.Required(CONF_OPTIONS): {
            vol.Required(ATTR_POSITION): whole_position,
        },
    }
)


def _position(state: State | None) -> float | None:
    """Return where a cover or valve is, if it says.

    Unavailable and unknown are not a position, even though a state restored
    at a start still carries the one from before the restart: that is a
    memory, not where the cover is. A cover that cannot be set to a position
    reports none at all.
    """
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        position = float(state.attributes[ATTR_CURRENT_POSITION])
    except KeyError, TypeError, ValueError:
        return None
    return position if math.isfinite(position) else None


def _reached(before: float, after: float, position: int) -> bool:
    """Tell whether moving from before to after reached the position.

    Getting there counts, and so does going past it: a cover moving quickly
    can report 20 and then 40 without ever reporting the 30 in between.
    Already there is not reaching it.
    """
    if before == position:
        return False
    return after == position or min(before, after) < position < max(before, after)


def _only_covers_and_valves(entity_ids: set[str]) -> set[str]:
    """Keep the covers and valves, as an area holds all sorts."""
    return {
        entity_id
        for entity_id in entity_ids
        if split_entity_id(entity_id)[0] in _DOMAINS
    }


# Everything here is called by the base class or by an event, so there is
# nothing public to count.
# pylint: disable-next=too-few-public-methods
class _PositionTracker(TargetEntityChangeTracker):
    """Watch a target's covers and valves for one getting to a position."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        position: int,
        on_reached: Callable[[Event[EventStateChangedData]], None],
    ) -> None:
        """Initialize the tracker."""
        super().__init__(hass, target_selection, entity_filter=_only_covers_and_valves)
        self._position = position
        self._on_reached = on_reached
        self._tracked: set[str] = set()
        self._unsub_changes: list[CALLBACK_TYPE] = []

    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Re-aim at the entities the target now covers.

        The base class re-expands the target on every entity, device and area
        registry event anywhere in the system, and almost none of those move
        this target.
        """
        if tracked_entities == self._tracked:
            return

        self._tracked = tracked_entities
        self._relisten()

    @callback
    def _relisten(self) -> None:
        """Listen for changes to exactly the entities being tracked.

        The new listener goes on before the old one comes off. Home Assistant
        keeps one shared tracker per event type: drop the last subscriber and
        it is torn down, taking with it events that have fired but not been
        dispatched yet.
        """
        previous = self._unsub_changes
        self._unsub_changes = []

        if self._tracked:
            self._unsub_changes = [
                async_track_state_change_event(
                    self._hass, list(self._tracked), self._entity_changed
                )
            ]

        for unsub in previous:
            unsub()

    @callback
    def _entity_changed(self, event: Event[EventStateChangedData]) -> None:
        """Compare where the cover or valve was with where it is now."""
        before = _position(event.data["old_state"])
        after = _position(event.data["new_state"])

        # Without a position on both sides there is no movement to judge: a
        # device coming back where it was did not just get there.
        if before is None or after is None:
            return

        if _reached(before, after, self._position):
            self._on_reached(event)

    def _unsubscribe(self) -> None:
        """Unsubscribe from everything, the base class' listeners included."""
        super()._unsubscribe()

        for unsub in self._unsub_changes:
            unsub()
        self._unsub_changes.clear()
        self._tracked = set()


class SpookTrigger(Trigger):
    """Spook trigger that fires when a cover or valve reaches a position.

    Home Assistant can tell you a cover opened or closed. Everything in
    between, the blinds at a third or the valve half open, is a position it
    reports but never announces.
    """

    trigger = "position_reached"

    _target: ConfigType
    _position: int

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
        self._position = options[ATTR_POSITION]
        self._target = config.target or {}

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def position_reached(event: Event[EventStateChangedData]) -> None:
            """Run the action for the cover or valve that got there."""
            entity_id = event.data["entity_id"]
            to_state = event.data["new_state"]
            payload: dict[str, Any] = {
                "entity_id": entity_id,
                "from_state": event.data["old_state"],
                "to_state": to_state,
                "position": self._position,
            }
            run_action(
                payload,
                f"{entity_id} reached position {self._position}",
                to_state.context if to_state else None,
            )

        tracker = _PositionTracker(
            self._hass, TargetSelection(self._target), self._position, position_reached
        )
        return await tracker.async_setup()
