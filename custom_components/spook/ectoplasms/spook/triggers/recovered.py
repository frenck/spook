"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import (
    CONF_FOR,
    CONF_OPTIONS,
    CONF_TARGET,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import Trigger
from homeassistant.util import dt as dt_util

from ....target_watching import watchable_target

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

# States that are not the entity saying anything about itself. An entity is
# only back when it reaches something that is neither of these.
_NOT_A_VALUE = (STATE_UNAVAILABLE, STATE_UNKNOWN)


def _a_real_absence(value: Any) -> timedelta:
    """Validate the duration, and refuse one nothing could be shorter than.

    Zero would fire on every flicker, and a reload of an integration takes
    every one of its entities through unavailable and back inside a second.
    That is the noise this trigger exists to filter out, so it cannot be
    switched off.
    """
    duration = cv.positive_time_period(value)
    if duration <= timedelta(0):
        message = "The duration must be longer than zero"
        raise vol.Invalid(message)
    return duration


_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): watchable_target,
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_FOR): _a_real_absence,
        },
    }
)


# Everything here is called by the base class or by an event, so there is
# nothing public to count.
# pylint: disable-next=too-few-public-methods
class _AbsenceTracker(TargetEntityChangeTracker):
    """Watch a target's entities and report the ones that come back.

    Remembers when each entity went unavailable and works out how long it was
    away when it returns, so there are no timers to keep: the only moment
    anything has to be decided is the moment it comes back.

    The registry listening and target re-expansion come from the base class,
    which calls back into `_handle_entities_update` whenever the set of
    targeted entities moves.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        duration: timedelta,
        on_return: Callable[
            [str, Event[EventStateChangedData], datetime, timedelta], None
        ],
    ) -> None:
        """Initialize the tracker."""
        super().__init__(hass, target_selection, entity_filter=lambda ids: ids)
        self._duration = duration
        self._on_return = on_return
        self._tracked: set[str] = set()
        self._gone_since: dict[str, datetime] = {}
        self._unsub_changes: list[CALLBACK_TYPE] = []
        self._unsub_started: CALLBACK_TYPE | None = None

        # Nothing is recorded until Home Assistant is up. A slow integration
        # sets up minutes into a start, and every entity it brings with it
        # goes from unavailable to a value at that moment. Recording through
        # the start would turn that into a recovery for each of them, timed
        # from whenever the entity was created.
        # `is_running` is not the question: that is already true while Home
        # Assistant is starting, which is the half of a start this is here to
        # sit out.
        self._recording = hass.state is CoreState.running
        if not self._recording:
            self._unsub_started = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._house_is_up
            )

    @callback
    def _house_is_up(self, _event: Event) -> None:
        """Start recording, taking the entities that are away with us."""
        self._unsub_started = None
        self._recording = True
        self._remember_who_is_away()

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
            self._gone_since.pop(entity_id, None)

        self._tracked = tracked_entities
        self._relisten()
        self._remember_who_is_away()

    @callback
    def _remember_who_is_away(self) -> None:
        """Note when the entities that are already away went.

        An entity that was unavailable before anybody was watching still has
        the moment it went in `last_changed`, so an automation reloaded while
        the device was down still reports how long the device was down, and
        not how long Spook has been looking.

        One sitting at unknown is left out. That state says nothing about how
        long it has been there, and guessing would be worse than waiting for
        the next spell.
        """
        if not self._recording:
            return

        for entity_id in self._tracked:
            if entity_id in self._gone_since:
                continue
            state = self._hass.states.get(entity_id)
            if state is not None and state.state == STATE_UNAVAILABLE:
                self._gone_since[entity_id] = state.last_changed

    @callback
    def _relisten(self) -> None:
        """Listen for changes to exactly the entities being tracked.

        The new listener goes on before the old one comes off. Home Assistant
        keeps one shared tracker per event type: drop the last subscriber and
        it is torn down, taking with it events that have fired but not been
        dispatched yet. Losing one here is losing the return itself.
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
        """Follow one entity through going away and coming back."""
        entity_id: str = event.data["entity_id"]

        if (new_state := event.data["new_state"]) is None:
            # Removed rather than returned. Whatever it was doing is over.
            self._gone_since.pop(entity_id, None)
            return

        if not self._recording:
            return

        if new_state.state == STATE_UNAVAILABLE:
            # `setdefault`, so a flip out to unknown and back does not restart
            # the clock on an absence that never ended.
            self._gone_since.setdefault(entity_id, new_state.last_changed)
            return

        if new_state.state == STATE_UNKNOWN:
            # Reachable again, with nothing to say yet. Not back.
            return

        if (gone_since := self._gone_since.pop(entity_id, None)) is None:
            # Never saw it go, so there is no absence to report the end of.
            # An entity that starts at unknown and gets its first value has
            # not recovered from anything.
            return

        if (gone_for := new_state.last_changed - gone_since) >= self._duration:
            self._on_return(entity_id, event, gone_since, gone_for)

    def _unsubscribe(self) -> None:
        """Unsubscribe from everything, the base class' listeners included."""
        super()._unsubscribe()

        if self._unsub_started is not None:
            self._unsub_started()
            self._unsub_started = None

        for unsub in self._unsub_changes:
            unsub()
        self._unsub_changes.clear()

        self._gone_since.clear()
        self._tracked = set()


class SpookTrigger(Trigger):
    """Spook trigger that fires when an entity comes back.

    Home Assistant will tell you the moment something goes unavailable, and
    the moment it returns, but not the difference between a blink and an
    outage. A router rebooting takes every device in the house through
    unavailable and back in seconds, which is why an automation on the return
    is usually more trouble than it is worth.

    This one only counts a return worth hearing about: the entity has to have
    been away for as long as you asked before coming back says anything.
    """

    trigger = "recovered"

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
        def entity_came_back(
            entity_id: str,
            event: Event[EventStateChangedData],
            gone_since: datetime,
            gone_for: timedelta,
        ) -> None:
            """Run the action for the entity that returned."""
            to_state = event.data["new_state"]

            run_action(
                {
                    "entity_id": entity_id,
                    "from_state": event.data["old_state"],
                    "to_state": to_state,
                    "for": self._duration,
                    "gone_since": dt_util.as_local(gone_since),
                    "gone_for": gone_for,
                },
                f"{entity_id} came back after {gone_for}",
                # Carried through, so Spook's own context conditions can still
                # tell whether a person was behind the return. Without it, a
                # device somebody switched back on reads as nobody's doing.
                to_state.context if to_state else None,
            )

        tracker = _AbsenceTracker(
            self._hass,
            TargetSelection(self._target),
            self._duration,
            entity_came_back,
        )
        return await tracker.async_setup()
