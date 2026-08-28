"""Spook - Your homie."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS, CONF_TARGET
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import Trigger
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.event import EventStateChangedData
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

CONF_CHANGES = "changes"
CONF_WITHIN = "within"

# One change is a change. Two in a row is the least that can be called going
# back and forth.
_MINIMUM_CHANGES = 2


def _flapping_count(value: Any) -> int:
    """Validate the number of changes, and refuse one that is not flapping."""
    changes = cv.positive_int(value)
    if changes < _MINIMUM_CHANGES:
        message = (
            f"It takes at least {_MINIMUM_CHANGES} changes to be going back "
            f"and forth, and this asks for {changes}"
        )
        raise vol.Invalid(message)
    return changes


def _window(value: Any) -> timedelta:
    """Validate the window, and refuse one nothing can happen inside."""
    within = cv.positive_time_period(value)
    if within <= timedelta(0):
        message = "The window must be longer than zero"
        raise vol.Invalid(message)
    return within


# `TARGET_FIELDS` is a plain mapping of schema fields, so it needs compiling
# before it can validate anything.
_TARGET_SCHEMA = vol.Schema(cv.TARGET_FIELDS)


def _watchable_target(value: Any) -> ConfigType:
    """Validate the target, and refuse one that names nothing.

    An empty target passes the field validation happily and then watches
    nothing at all: a trigger that loads and can never fire. Core's own target
    tracking helper raises on this for the same reason.
    """
    target: ConfigType = _TARGET_SCHEMA(value)
    if not TargetSelection(target).has_any_target:
        message = (
            "The target must name at least one entity, device, area, floor or label"
        )
        raise vol.Invalid(message)
    return target


_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): _watchable_target,
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_CHANGES): _flapping_count,
            vol.Required(CONF_WITHIN): _window,
        },
    }
)


@dataclass(slots=True)
class _Recent:
    """The last few changes to one entity, and whether it has been reported.

    The deque is capped at the number of changes being looked for, so the
    oldest one falls off by itself and the question is only ever whether the
    ones still in hand happened close enough together. No pruning, and no
    growth on an entity that changes all day.
    """

    seen: deque[datetime]
    reported: bool = False


# Everything here is called by the base class or by an event, so there is
# nothing public to count.
# pylint: disable-next=too-few-public-methods
class _FlappingEntityTracker(TargetEntityChangeTracker):
    """Watch a target's entities and report the ones that will not settle.

    Changes of state, not writes: an entity reporting the same value over and
    over is chatty, not flapping. Going to `unavailable` and back does count,
    which is the case this exists for.

    The registry listening and target re-expansion come from the base class,
    which calls back into `_handle_entities_update` whenever the set of
    targeted entities moves.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        changes: int,
        within: timedelta,
        on_flapping: Callable[[str, Event[EventStateChangedData]], None],
    ) -> None:
        """Initialize the tracker."""
        super().__init__(hass, target_selection, entity_filter=lambda ids: ids)
        self._changes = changes
        self._within = within
        self._on_flapping = on_flapping
        self._tracked: set[str] = set()
        self._recent: dict[str, _Recent] = {}
        self._unsub_changes: list[CALLBACK_TYPE] = []

    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Re-aim at the entities the target now covers.

        The base class re-expands the target on every entity, device and area
        registry event anywhere in the system, and almost none of those move
        this target. Tearing down and rebuilding the listeners each time would
        be work for nothing.
        """
        if tracked_entities == self._tracked:
            return

        for entity_id in self._tracked - tracked_entities:
            self._recent.pop(entity_id, None)

        self._tracked = tracked_entities
        self._relisten()

    @callback
    def _relisten(self) -> None:
        """Listen for changes to exactly the entities being tracked.

        The new listener goes on before the old one comes off. Home Assistant
        keeps one shared tracker per event type: drop the last subscriber and
        it is torn down, taking with it events that have fired but not been
        dispatched yet. Core's own target tracker orders it this way for the
        same reason.
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
        """Count a change, and report an entity that has had too many."""
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        if old_state is None or new_state is None:
            # An entity arriving or leaving is not it going back and forth.
            return

        if old_state.state == new_state.state:
            # An attribute moved and the state did not. Chatty, not flapping.
            return

        entity_id = event.data["entity_id"]
        recent = self._recent.get(entity_id)
        if recent is None:
            recent = self._recent[entity_id] = _Recent(seen=deque(maxlen=self._changes))

        recent.seen.append(dt_util.utcnow())

        if len(recent.seen) < self._changes or (
            recent.seen[-1] - recent.seen[0] > self._within
        ):
            # Not enough changes in hand, or the oldest of them is too long
            # ago. Either way it has settled since, so it can be reported
            # again when it starts up.
            recent.reported = False
            return

        if recent.reported:
            # Already said so. Reporting every further change would be a
            # storm of alerts about a storm.
            return

        recent.reported = True
        self._on_flapping(entity_id, event)

    def _unsubscribe(self) -> None:
        """Unsubscribe from everything, the base class' listeners included."""
        super()._unsubscribe()

        for unsub in self._unsub_changes:
            unsub()
        self._unsub_changes.clear()

        self._recent.clear()
        self._tracked = set()


class SpookTrigger(Trigger):
    """Spook trigger that fires when an entity will not settle.

    A sensor that goes on and off and on again, a device that drops off the
    network and comes back, a binary sensor sitting right on its threshold.
    Each change on its own looks fine, and Home Assistant has no way to say
    "this one has changed five times in five minutes and something is wrong
    with it".
    """

    trigger = "flapping"

    _changes: int
    _within: timedelta
    _target: ConfigType

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
        self._changes = options[CONF_CHANGES]
        self._within = options[CONF_WITHIN]
        self._target = config.target or {}

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def entity_is_flapping(
            entity_id: str,
            event: Event[EventStateChangedData],
        ) -> None:
            """Run the action for the entity that will not settle."""
            to_state = event.data["new_state"]

            run_action(
                {
                    "entity_id": entity_id,
                    "from_state": event.data["old_state"],
                    "to_state": to_state,
                    "changes": self._changes,
                    "within": self._within,
                },
                f"{entity_id} changed {self._changes} times in {self._within}",
                to_state.context if to_state else None,
            )

        tracker = _FlappingEntityTracker(
            self._hass,
            TargetSelection(self._target),
            self._changes,
            self._within,
            entity_is_flapping,
        )
        return await tracker.async_setup()
