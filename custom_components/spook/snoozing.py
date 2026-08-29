"""Spook - Your homie. Automations that are off for a while, not off for good."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STARTED,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from homeassistant.core import CALLBACK_TYPE, Context, Event, HomeAssistant
    from homeassistant.helpers.event import EventStateChangedData

DATA_SNOOZING: HassKey[Snoozing] = HassKey("spook_snoozing")

STORAGE_KEY = f"{DOMAIN}.snoozing"
STORAGE_VERSION = 1


class Snoozing:
    """Keeps automations off until their time is up, restarts included.

    An automation that is off stays off across a restart, which is the whole
    reason this has to be written down rather than left in a timer. Home
    Assistant coming back up with an automation still asleep and nothing left
    to wake it is how a snooze becomes a disable nobody remembers making.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the register."""
        self._hass = hass
        self._store: Store[dict[str, str]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._until: dict[str, datetime] = {}
        self._timers: dict[str, CALLBACK_TYPE] = {}
        self._unsub_watching: CALLBACK_TYPE | None = None
        self._unsub_started: CALLBACK_TYPE | None = None
        self._stopped = False

    async def async_start(self) -> CALLBACK_TYPE:
        """Read back what was asleep, and take it from there."""
        stored = await self._store.async_load() or {}

        if self._stopped:
            # Unloaded while the store was being read. Stopping cannot reach
            # into a coroutine that is waiting, so anything arming something
            # after an `await` has to look for itself. Here that is the
            # listener below; the timers and the state watch refuse on their
            # own.
            return self.async_stop

        self._until = {
            entity_id: parsed
            for entity_id, until in stored.items()
            if (parsed := dt_util.parse_datetime(until)) is not None
        }

        # Waking things up needs the automations to exist, and at setup they
        # may not yet. Anything already asleep waits for Home Assistant to say
        # it has finished starting.
        if self._hass.state is CoreState.running:
            await self._async_catch_up()
        else:
            self._unsub_started = self._hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._async_started
            )

        return self.async_stop

    @callback
    def async_stop(self) -> None:
        """Stop waiting, without waking anything.

        What is asleep stays written down, so it is picked up again next time
        rather than left off for good.
        """
        self._stopped = True

        for entity_id in list(self._timers):
            self._async_cancel_timer(entity_id)

        if self._unsub_watching is not None:
            self._unsub_watching()
            self._unsub_watching = None

        if self._unsub_started is not None:
            self._unsub_started()
            self._unsub_started = None

    async def async_snooze(
        self,
        entity_id: str,
        duration: timedelta,
        context: Context | None = None,
    ) -> None:
        """Turn an automation off, and arrange for it to come back on.

        Asking again for one already asleep moves its wake-up time, rather
        than being turned away for being off: it is off because of this, and
        asking for longer is the ordinary way to use it.
        """
        asleep = entity_id in self._until
        state = self._hass.states.get(entity_id)

        if not asleep and (state is None or state.state != STATE_ON):
            # Turning it on later would be a change nobody asked for: it was
            # off before this, and this is not the thing that put it there.
            LOGGER.warning(
                "Spook did not snooze %s because it is not on, "
                "and waking it would turn it on",
                entity_id,
            )
            return

        self._until[entity_id] = dt_util.utcnow() + duration
        await self._async_save()

        # Unloaded while that was saving leaves both of these refusing, and
        # the automation is still turned off below: it is written down, so the
        # next start picks it up. Only the waiting goes.
        self._async_rearm(entity_id)
        self._async_watch()

        # Turned off every time, including one already asleep. Skipping it
        # would save nothing observable and opens a gap: somebody turning the
        # automation on by hand cancels the snooze through a state event, and
        # a fresh snooze arriving before that event lands would find it still
        # written down as asleep and leave it running with a wake-up time.
        await self._hass.services.async_call(
            AUTOMATION_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            context=context,
        )

    @callback
    def async_until(self, entity_id: str) -> datetime | None:
        """Return when an automation is due to wake, if it is asleep."""
        return self._until.get(entity_id)

    async def _async_started(self, _event: Event) -> None:
        """Home Assistant has finished starting, so the automations are here."""
        self._unsub_started = None
        await self._async_catch_up()

    async def _async_catch_up(self) -> None:
        """Sort out everything that was asleep when the lights went out."""
        now = dt_util.utcnow()

        for entity_id, until in list(self._until.items()):
            if self._stopped:
                # Unloaded partway through, waking one of them.
                return

            state = self._hass.states.get(entity_id)

            if state is None:
                # Gone while Home Assistant was down. Nothing to wake.
                LOGGER.debug("Spook forgot a snooze for missing %s", entity_id)
                self._until.pop(entity_id, None)
            elif state.state == STATE_ON:
                # Somebody turned it on in the meantime, which says more about
                # what they want than the snooze does.
                self._until.pop(entity_id, None)
            elif until <= now:
                await self._async_wake(entity_id, until)
            else:
                self._async_rearm(entity_id)

        await self._async_save()
        self._async_watch()

    @callback
    def _async_rearm(self, entity_id: str) -> None:
        """Wait until this one is due.

        In UTC, because the wait is a fixed instant and adding a duration to a
        local time is wall-clock arithmetic: an hour out, twice a year.
        """
        self._async_cancel_timer(entity_id)

        if self._stopped or (until := self._until.get(entity_id)) is None:
            return

        self._timers[entity_id] = async_track_point_in_utc_time(
            self._hass, self._async_due(entity_id, until), until
        )

    @callback
    def _async_due(self, entity_id: str, until: datetime) -> CALLBACK_TYPE:
        """Return the callback that wakes one automation at this time.

        Carrying the time it was set for, because cancelling a wait does not
        recall a callback already on its way. One that arrives after somebody
        asked for longer would otherwise drop the new wait and wake the
        automation at the old time.
        """

        async def _wake(_now: datetime) -> None:
            if self._until.get(entity_id) != until:
                return

            self._timers.pop(entity_id, None)
            await self._async_wake(entity_id, until)

        return _wake

    async def _async_wake(self, entity_id: str, until: datetime) -> None:
        """Put an automation back on, its time being up.

        The record goes first, so this wake-up call is not read as somebody
        turning the automation on by hand, and comes back if turning it on
        fails. An automation left off with nothing written down is the
        disable-nobody-remembers this whole thing exists to prevent.
        """
        self._until.pop(entity_id, None)
        self._async_cancel_timer(entity_id)
        self._async_watch()

        try:
            await self._hass.services.async_call(
                AUTOMATION_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
        except HomeAssistantError:
            LOGGER.exception(
                "Spook could not wake %s and left the snooze on the books, "
                "to try again after a restart",
                entity_id,
            )

            # Unless somebody asked for a fresh one while that was failing,
            # in which case theirs is the newer word on it.
            if entity_id not in self._until:
                self._until[entity_id] = until
                self._async_watch()

            return

        await self._async_save()

    @callback
    def _async_watch(self) -> None:
        """Listen for anything asleep being turned on by somebody else.

        Which cancels the snooze: turning it on is a clearer statement of what
        somebody wants than a wake-up time they set earlier.

        The record is dropped before this trigger's own wake-up call, so the
        entity is no longer being watched by the time that arrives and it does
        not cancel itself.
        """
        previous = self._unsub_watching
        self._unsub_watching = None

        if self._until and not self._stopped:
            self._unsub_watching = async_track_state_change_event(
                self._hass, list(self._until), self._async_woken_by_hand
            )

        if previous is not None:
            previous()

    @callback
    def _async_woken_by_hand(self, event: Event[EventStateChangedData]) -> None:
        """Forget a snooze for an automation somebody has turned back on.

        Or removed entirely. A reload only makes an automation unavailable for
        a moment, so a state that is gone for good means the automation is, and
        a record for something that no longer exists is dead weight in the
        store.
        """
        new_state = event.data["new_state"]
        if new_state is not None and new_state.state != STATE_ON:
            return

        entity_id = event.data[ATTR_ENTITY_ID]
        if self._until.pop(entity_id, None) is None:
            return

        self._async_cancel_timer(entity_id)
        self._async_watch()
        self._hass.async_create_task(self._async_save())

    @callback
    def _async_cancel_timer(self, entity_id: str) -> None:
        """Drop the pending wait for one automation, if there is one."""
        if (timer := self._timers.pop(entity_id, None)) is not None:
            timer()

    async def _async_save(self) -> None:
        """Write down what is asleep."""
        await self._store.async_save(
            {entity_id: until.isoformat() for entity_id, until in self._until.items()}
        )


@callback
def async_get_snoozing(hass: HomeAssistant) -> Snoozing:
    """Return the shared register."""
    return hass.data[DATA_SNOOZING]


async def async_setup_snoozing(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Start keeping track of what is asleep, and return the way to stop."""
    snoozing = hass.data[DATA_SNOOZING] = Snoozing(hass)
    stop = await snoozing.async_start()

    @callback
    def _unload() -> None:
        """Stop, and take the register with it.

        Leaving a stopped register behind would hand the next thing that asks
        one that no longer keeps time.
        """
        stop()
        hass.data.pop(DATA_SNOOZING, None)

    return _unload
