"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_FOR, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_state_report_event,
)
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import Trigger
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType


def _quiet_period(value: Any) -> timedelta:
    """Validate the duration, and refuse one that can never elapse.

    A zero duration would put the deadline on the moment the entity last
    spoke, which is always in the past, so the trigger would load and then
    sit there doing nothing at all.
    """
    duration = cv.positive_time_period(value)
    if duration <= timedelta(0):
        message = "The duration must be longer than zero"
        raise vol.Invalid(message)
    return duration


# `TARGET_FIELDS` is a plain mapping of schema fields, so it needs compiling
# before it can validate anything.
_TARGET_SCHEMA = vol.Schema(cv.TARGET_FIELDS)


def _watchable_target(value: Any) -> ConfigType:
    """Validate the target, and refuse one that names nothing.

    An empty target passes the field validation happily and then watches
    nothing at all: a trigger that loads and can never fire. Core's own
    target tracking helper raises on this for the same reason.
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
            vol.Required(CONF_FOR): _quiet_period,
        },
    }
)


# Everything here is called by the base class or by an event, so there is
# nothing public to count.
# pylint: disable-next=too-few-public-methods
class _QuietEntityTracker(TargetEntityChangeTracker):
    """Watch a target's entities and report the ones that fall silent.

    Silence, not stillness: an entity that keeps reporting the same value is
    alive and well. This watches `last_reported`, which moves on every write,
    changed or not, so what it catches is nothing writing at all.

    The registry listening and target re-expansion come from the base class,
    which calls back into `_handle_entities_update` whenever the set of
    targeted entities moves.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        duration: timedelta,
        on_quiet: Callable[[str, datetime], None],
    ) -> None:
        """Initialize the tracker."""
        super().__init__(hass, target_selection, entity_filter=lambda ids: ids)
        self._duration = duration
        self._on_quiet = on_quiet
        self._tracked: set[str] = set()
        self._timers: dict[str, CALLBACK_TYPE] = {}
        self._unsub_writes: list[CALLBACK_TYPE] = []

    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Re-aim at the entities the target now covers.

        The base class re-expands the target on every entity, device and area
        registry event anywhere in the system, and almost none of those move
        this target. Tearing down and rebuilding the write listeners each time
        would be work for nothing.
        """
        if tracked_entities == self._tracked:
            return

        for entity_id in self._tracked - tracked_entities:
            self._cancel_timer(entity_id)

        self._tracked = tracked_entities
        self._relisten()

        # Entities already quiet when the target picks them up are left alone.
        # Firing for them would mean every automation reload replays whatever
        # has gone silent since, which is noise rather than news.
        for entity_id in tracked_entities:
            if entity_id not in self._timers:
                self._rearm(entity_id)

    @callback
    def _relisten(self) -> None:
        """Listen for writes to exactly the entities being tracked.

        A write that changes the state and a write that does not are two
        different events, and only the pair of them adds up to "something
        wrote to this entity".

        The new listeners go on before the old ones come off. Home Assistant
        keeps one shared tracker per event type: drop the last subscriber and
        it is torn down, taking with it events that have fired but not been
        dispatched yet. Core's own target tracker orders it this way for that
        reason, and losing a write here would mean an entity reported as
        silent when it had just spoken.
        """
        previous = self._unsub_writes
        self._unsub_writes = []

        if self._tracked:
            entity_ids = list(self._tracked)
            self._unsub_writes = [
                async_track_state_change_event(
                    self._hass, entity_ids, self._entity_wrote
                ),
                async_track_state_report_event(
                    self._hass, entity_ids, self._entity_wrote
                ),
            ]

        for unsub in previous:
            unsub()

    @callback
    def _entity_wrote(self, event: Event) -> None:
        """Start the wait over: this entity has just spoken."""
        self._rearm(event.data["entity_id"])

    @callback
    def _rearm(self, entity_id: str) -> None:
        """Wait until this entity would have been quiet for the whole duration."""
        self._cancel_timer(entity_id)

        if (state := self._hass.states.get(entity_id)) is None:
            return

        # Worked out in UTC on purpose. Adding an hour to a local time is
        # wall-clock arithmetic, and on the night the clocks go back that
        # hour is two hours of real waiting.
        deadline = state.last_reported + self._duration
        if deadline <= dt_util.utcnow():
            # Already past it, so this entity was quiet before we looked.
            return

        self._timers[entity_id] = async_track_point_in_time(
            self._hass,
            partial(self._went_quiet, entity_id, state.last_reported),
            deadline,
        )

    @callback
    def _went_quiet(
        self,
        entity_id: str,
        last_reported: datetime,
        _fired_at: datetime,
    ) -> None:
        """Report an entity that has now been quiet for the whole duration.

        The moment it last spoke is carried through from when the wait was
        set, rather than worked back out of the time the callback is handed.
        That one arrives in local time, and subtracting a duration from a
        local time is wall-clock arithmetic: wrong by an hour, twice a year.
        Not doing the arithmetic beats doing it correctly.
        """
        self._timers.pop(entity_id, None)
        self._on_quiet(entity_id, last_reported)

    @callback
    def _cancel_timer(self, entity_id: str) -> None:
        """Drop the pending wait for one entity, if there is one."""
        if (timer := self._timers.pop(entity_id, None)) is not None:
            timer()

    def _unsubscribe(self) -> None:
        """Unsubscribe from everything, the base class' listeners included."""
        super()._unsubscribe()

        for unsub in self._unsub_writes:
            unsub()
        self._unsub_writes.clear()

        for entity_id in list(self._timers):
            self._cancel_timer(entity_id)

        self._tracked = set()


class SpookTrigger(Trigger):
    """Spook trigger that fires when an entity falls silent.

    Home Assistant can tell you an entity went unavailable, but plenty of
    things die without ever saying so: a sensor whose integration quietly
    stopped polling, a battery device that dropped off the network, an MQTT
    topic nobody is publishing to any more. The state sits there looking
    perfectly fine, holding a number from last Tuesday.
    """

    trigger = "stale"

    _duration: timedelta
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
        self._duration = options[CONF_FOR]
        self._target = config.target or {}

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def entity_went_quiet(entity_id: str, last_reported: datetime) -> None:
            """Run the action for the entity that fell silent."""
            run_action(
                {
                    "entity_id": entity_id,
                    "for": self._duration,
                    "last_reported": dt_util.as_local(last_reported),
                },
                f"{entity_id} reported nothing for {self._duration}",
            )

        tracker = _QuietEntityTracker(
            self._hass,
            TargetSelection(self._target),
            self._duration,
            entity_went_quiet,
        )
        return await tracker.async_setup()
