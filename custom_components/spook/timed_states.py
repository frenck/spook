"""Spook - Your homie. Automations held in a state for a while, not for good."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STARTED,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import datetime, timedelta

    from homeassistant.core import CALLBACK_TYPE, Context, Event, HomeAssistant
    from homeassistant.helpers.event import EventStateChangedData

DATA_TIMED_STATES: HassKey[TimedStates] = HassKey("spook_timed_states")

STORAGE_KEY = f"{DOMAIN}.timed_states"
STORAGE_VERSION = 1

# What this register was called when it only knew how to snooze. Records under
# that name are taken over once and the file is dropped.
LEGACY_STORAGE_KEY = f"{DOMAIN}.snoozing"

# Both mean the same thing to a move: it did not happen. A script calling one
# of these actions can be stopped mid-call, and that is not a shutdown, so the
# record has to be sorted out either way before the caller hears about it.
_MOVE_INTERRUPTED = (HomeAssistantError, asyncio.CancelledError)


def a_stretch_of_time(value: Any) -> timedelta:
    """Validate a duration that is actually a duration.

    `cv.positive_time_period` counts nothing at all as positive, and holding
    an automation for nothing is one turned over and straight back: a pulse
    through everything watching it, in exchange for nothing at all.
    """
    period = cv.positive_time_period(value)

    if not period:
        msg = "duration must be longer than nothing"
        raise vol.Invalid(msg)

    return period


@dataclass(frozen=True, slots=True)
class _Held:
    """One automation being kept in a state, and until when."""

    until: datetime
    state: str

    @property
    def restore_to(self) -> str:
        """Return the state it goes back to when the time is up.

        An automation is on or it is off, so the way back is whichever of the
        two it is not being held in.
        """
        return STATE_OFF if self.state == STATE_ON else STATE_ON


# Three of the attributes below are subscriptions, each cancelled in its own
# way and at its own moment, so folding them into one bag would cost more than
# the count saves.
class TimedStates:  # pylint: disable=too-many-instance-attributes
    """Keeps automations in a state until their time is up, restarts included.

    An automation keeps whatever state it had across a restart, which is the
    whole reason this has to be written down rather than left in a timer. Home
    Assistant coming back up with an automation still held and nothing left to
    put it back is how a snooze becomes a disable nobody remembers making.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the register."""
        self._hass = hass
        self._store: Store[dict[str, dict[str, str]]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self._held: dict[str, _Held] = {}
        self._timers: dict[str, CALLBACK_TYPE] = {}
        self._unsub_watching: CALLBACK_TYPE | None = None
        self._unsub_started: CALLBACK_TYPE | None = None
        self._unsub_registry: CALLBACK_TYPE | None = None
        self._moving: dict[str, list[str]] = {}
        self._stopped = False

    async def async_start(self) -> CALLBACK_TYPE:
        """Read back what was being held, and take it from there."""
        stored = await self._async_load()

        if self._stopped:
            # Unloaded while the store was being read. Stopping cannot reach
            # into a coroutine that is waiting, so anything arming something
            # after an `await` has to look for itself. Here that is the
            # listener below; the timers and the state watch refuse on their
            # own.
            return self.async_stop

        self._held = {
            entity_id: _Held(until=parsed, state=record["state"])
            for entity_id, record in stored.items()
            if (parsed := dt_util.parse_datetime(record["until"])) is not None
        }

        # Records are filed under an entity ID, so the register has to hear
        # about the ones that change or go away.
        self._unsub_registry = self._hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._async_registry_changed
        )

        # Putting things back needs the automations to exist, and at setup they
        # may not yet. Anything still held waits for Home Assistant to say it
        # has finished starting.
        if self._hass.state is CoreState.running:
            await self._async_catch_up()
        else:
            self._unsub_started = self._hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._async_started
            )

        return self.async_stop

    async def _async_load(self) -> dict[str, dict[str, str]]:
        """Read the records, taking over from the snooze-only store if need be.

        A store migration only runs for the file being loaded, and this one is
        under its own name, so the old file has to be picked up by hand or
        every snooze made before the upgrade is silently dropped: automations
        left off with nothing to turn them back on.
        """
        if (stored := await self._store.async_load()) is not None:
            return stored

        legacy: Store[dict[str, str]] = Store(self._hass, 1, LEGACY_STORAGE_KEY)
        if (snoozes := await legacy.async_load()) is None:
            return {}

        LOGGER.debug("Spook took over %s snoozes written down before", len(snoozes))

        # Everything in there was a snooze, so an automation being held off.
        taken_over = {
            entity_id: {"until": until, "state": STATE_OFF}
            for entity_id, until in snoozes.items()
        }
        await self._store.async_save(taken_over)
        await legacy.async_remove()

        return taken_over

    @callback
    def async_stop(self) -> None:
        """Stop waiting, without putting anything back.

        What is held stays written down, so it is picked up again next time
        rather than left where it is for good.
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

        if self._unsub_registry is not None:
            self._unsub_registry()
            self._unsub_registry = None

    async def async_hold(
        self,
        entity_id: str,
        duration: timedelta,
        state: str,
        context: Context | None = None,
    ) -> None:
        """Put an automation in a state, and arrange for it to come back.

        Asking again for one already being held moves the time it comes back,
        rather than being turned away for already being in that state: it is
        in it because of this, and asking for longer is the ordinary way to
        use it.
        """
        held = self._held.get(entity_id)
        if held is None and self._is_in(entity_id, state):
            # Putting it back later would be a change nobody asked for: it was
            # like this before, and this is not the thing that made it so.
            LOGGER.warning(
                "Spook left %s alone because it is already %s, "
                "and putting it back would change it",
                entity_id,
                state,
            )
            return

        try:
            deadline = dt_util.utcnow() + duration
        except OverflowError as err:
            # Time periods run further than datetimes do, so a big enough
            # number of days lands past the end of the calendar. Worked out
            # here rather than at the door, because the answer depends on what
            # time it is by the time the call actually happens.
            msg = f"Cannot hold {entity_id} until a time that does not exist"
            raise ServiceValidationError(msg) from err

        holding = _Held(until=deadline, state=state)
        self._held[entity_id] = holding
        await self._async_save()

        if held is None and not self._is_in(entity_id, holding.restore_to):
            # Changed by somebody else while that was saving, and Spook does
            # not put back what it did not move.
            self._async_forget(entity_id)
            return

        if self._held.get(entity_id) != holding:
            # Somebody put the automation back while that was saving, which
            # cancels the hold. Extending one is where that can happen, the
            # automation being held and watched at the time. Moving it now
            # would leave it there with nothing to put it back.
            return

        # Unloaded while that was saving leaves this refusing, and the
        # automation is still moved below: it is written down, so the next
        # start picks it up. Only the waiting goes.
        self._async_watch()

        # Moved every time, including one already held. Skipping it would save
        # nothing observable and opens a gap: somebody putting the automation
        # back by hand cancels the hold through a state event, and a fresh one
        # arriving before that event lands would find it still written down as
        # held and leave it where it is with a time to come back.
        try:
            await self._async_set(entity_id, holding.state, context)
        except _MOVE_INTERRUPTED:
            self._async_move_failed(entity_id, holding, held)
            raise

        if (current := self._held.get(entity_id)) != holding:
            await self._async_give_way(entity_id, holding, current, context)
            return

        # And only now the waiting, because a hold short enough to come due
        # while that was happening would otherwise put the automation back
        # before this moved it, leaving it moved with nothing to put it back.
        # A deadline that has already passed by this point simply fires at
        # once.
        self._async_rearm(entity_id)

    async def _async_set(
        self,
        entity_id: str,
        state: str,
        context: Context | None = None,
    ) -> None:
        """Put an automation in a state and wait for that to have happened.

        Marked with where it is going while it happens, so the state that
        comes of it is not read as somebody reaching for the switch. Marking
        the entity alone would be too much: a person turning it the other way
        during the call is exactly the thing that has to keep counting, and
        that is the one an entity-wide mark would swallow.
        """
        with self._moving_to(entity_id, state):
            await self._hass.services.async_call(
                AUTOMATION_DOMAIN,
                SERVICE_TURN_ON if state == STATE_ON else SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
                context=context,
            )

    @contextlib.contextmanager
    def _moving_to(self, entity_id: str, state: str) -> Iterator[None]:
        """Note where Spook is putting an automation, for as long as it takes.

        A list rather than one state per automation, because two calls can
        have a move in flight for the same one and each has to take its own
        mark back rather than the other's.
        """
        moves = self._moving.setdefault(entity_id, [])
        moves.append(state)

        try:
            yield
        finally:
            moves.remove(state)

            if not moves:
                self._moving.pop(entity_id, None)

    @callback
    def _async_move_failed(
        self,
        entity_id: str,
        holding: _Held,
        before: _Held | None,
    ) -> None:
        """Sort out the record for a move that did not happen."""
        if self._held.get(entity_id) != holding:
            # Somebody else's record by now, and theirs to look after.
            return

        if self._is_in(entity_id, holding.restore_to):
            # Never moved, so this call leaves no trace: the register goes
            # back to whatever it said before, which is an older hold still
            # standing or nothing at all. Keeping this one would have Spook
            # change an automation it never touched.
            self._async_put_back(entity_id, before)
            return

        # Moved already, by the hold this one was extending. The deadline is
        # written down, and a record with nothing waiting on it is an
        # automation stuck until a restart: the wait it had was let go to make
        # room for this one.
        self._async_rearm(entity_id)

    async def _async_give_way(
        self,
        entity_id: str,
        holding: _Held,
        current: _Held | None,
        context: Context | None,
    ) -> None:
        """Hand the automation over, this call's record having been replaced."""
        if current is None:
            # Put back by hand between the last check and the call landing,
            # which cancels the hold. The move went through anyway, so it is
            # taken back here: leaving it would be an automation held with
            # nothing left to put it back.
            await self._async_set(entity_id, holding.restore_to, context)
            return

        if not self._is_in(entity_id, current.state):
            # A newer hold stands, and the automation is not where that one
            # wants it: this move landed after theirs did and undid it.
            # Whichever way round they asked for is the one that counts.
            await self._async_set(entity_id, current.state, context)

    @callback
    def _is_in(self, entity_id: str, state: str) -> bool:
        """Return whether an automation is in a state right now."""
        current = self._hass.states.get(entity_id)
        return current is not None and current.state == state

    @callback
    def async_until(self, entity_id: str) -> datetime | None:
        """Return when an automation comes back, if it is being held."""
        held = self._held.get(entity_id)
        return held.until if held is not None else None

    async def _async_started(self, _event: Event) -> None:
        """Home Assistant has finished starting, so the automations are here."""
        self._unsub_started = None
        await self._async_catch_up()

    async def _async_catch_up(self) -> None:
        """Sort out everything that was held when the lights went out."""
        now = dt_util.utcnow()

        # Watched from the outset rather than only at the end, because the end
        # is a store write and somebody putting an automation back during it
        # would go unseen, leaving a record counting down for something that
        # is already back.
        self._async_watch()

        for entity_id, held in list(self._held.items()):
            if self._stopped:
                # Unloaded partway through, putting one of them back.
                return

            state = self._hass.states.get(entity_id)

            if state is None and er.async_get(self._hass).async_get(entity_id) is None:
                # Gone while Home Assistant was down. Nothing to put back.
                LOGGER.debug("Spook forgot a timed state for missing %s", entity_id)
                self._held.pop(entity_id, None)
            elif state is None:
                # No state but still in the registry, so disabled rather than
                # gone. The record waits, and the watch sees to it if it comes
                # back; the wait below is armed either way so a deadline that
                # passes while it is away is not lost.
                self._async_rearm(entity_id)
            elif state.state == held.restore_to:
                # Somebody put it back in the meantime, which says more about
                # what they want than the record does.
                self._held.pop(entity_id, None)
            elif held.until <= now:
                await self._async_restore(entity_id, held)
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

        if self._stopped or (held := self._held.get(entity_id)) is None:
            return

        self._timers[entity_id] = async_track_point_in_utc_time(
            self._hass, self._async_due(entity_id, held), held.until
        )

    @callback
    def _async_due(self, entity_id: str, held: _Held) -> CALLBACK_TYPE:
        """Return the callback that puts one automation back at this time.

        Carrying the record it was set for, because cancelling a wait does not
        recall a callback already on its way. One that arrives after somebody
        asked for longer would otherwise drop the new wait and put the
        automation back at the old time.

        Nor does cancelling recall one that came due in the same breath as the
        unload, which is why the flag is worth another look here.
        """

        async def _restore(_now: datetime) -> None:
            if self._stopped or self._held.get(entity_id) != held:
                return

            self._timers.pop(entity_id, None)
            await self._async_restore(entity_id, held)

        return _restore

    async def _async_restore(self, entity_id: str, held: _Held) -> None:
        """Put an automation back, its time being up.

        The record stays put until the automation is actually back. Removing
        it first and putting it back on failure reads the same most of the
        time, but not when the failure is the process going away: a
        cancellation partway leaves nothing written down, and an automation
        held with nothing written down is the change-nobody-remembers this
        whole thing exists to prevent.
        """
        if self._stopped or self._held.get(entity_id) != held:
            # A second chance is handed to the loop, so both unloading and
            # somebody putting the automation back can happen between that
            # being arranged and this getting to run.
            return

        self._async_cancel_timer(entity_id)

        try:
            await self._async_set(entity_id, held.restore_to)
        except HomeAssistantError:
            LOGGER.exception(
                "Spook could not put %s back and left the record on the books, "
                "to try again after a restart",
                entity_id,
            )
            return

        if not self._is_in(entity_id, held.restore_to):
            # Entity services quietly pass over whatever is unavailable and
            # come back as though all was well, so a call landing in the
            # middle of a reload changes nothing. The record stays, and the
            # watch below has another go once the automation is back.
            LOGGER.debug(
                "Spook could not put %s back, which is not there at the moment",
                entity_id,
            )
            return

        if (asked_for := self._held.get(entity_id)) != held:
            # Asked for again while this was putting it back, so theirs is the
            # newer word on it and the automation belongs held. It was just
            # put back, so that has to be undone, and in whichever direction
            # the newer record asks for rather than this one's.
            #
            # No record at all does not happen here: losing one midway takes
            # the automation going with it, and the check above has already
            # turned back for that.
            if asked_for is not None:
                await self._async_set(entity_id, asked_for.state)

            return

        del self._held[entity_id]
        await self._async_save()
        self._async_watch()

    @callback
    def _async_registry_changed(
        self,
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Follow a renamed automation, and let go of a removed one.

        The record is filed under an entity ID, and an entity ID is something
        people change. Following it here keeps the record on the automation
        rather than on the name it happened to have.
        """
        data = event.data
        entity_id = data["entity_id"]

        if data["action"] == "remove":
            # Nothing left to put back, so the record is dead weight.
            self._async_forget(entity_id)
            return

        if old_entity_id := data.get("old_entity_id"):
            if (held := self._held.pop(old_entity_id, None)) is None:
                return

            self._async_cancel_timer(old_entity_id)
            self._held[entity_id] = held
            self._async_rearm(entity_id)
            self._async_watch()
            self._hass.async_create_task(self._async_save())

    @callback
    def _async_put_back(self, entity_id: str, held: _Held | None) -> None:
        """Undo a record a call wrote, leaving whatever was there before it."""
        if held is None:
            self._async_forget(entity_id)
            return

        self._held[entity_id] = held
        self._async_rearm(entity_id)
        self._async_watch()
        self._hass.async_create_task(self._async_save())

    @callback
    def _async_forget(self, entity_id: str) -> None:
        """Drop a record, there being no automation left to put back."""
        if self._held.pop(entity_id, None) is None:
            return

        self._async_cancel_timer(entity_id)
        self._async_watch()
        self._hass.async_create_task(self._async_save())

    @callback
    def _async_watch(self) -> None:
        """Listen to everything being held.

        For two things. Somebody putting one back, which cancels the hold: it
        is a clearer statement of what they want than a time set earlier. And
        one coming back from wherever it was, which is the second chance for a
        call that arrived while it was away.
        """
        previous = self._unsub_watching
        self._unsub_watching = None

        if self._held and not self._stopped:
            self._unsub_watching = async_track_state_change_event(
                self._hass, list(self._held), self._async_state_changed
            )

        if previous is not None:
            previous()

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Deal with something being held changing state.

        A state that is gone usually says nothing here: a rename takes the old
        one away as surely as a delete does, and telling those apart is what
        the registry is for. Usually, because a YAML automation written
        without an `id` has no registry entry to be renamed in, and for those
        a state gone for good is the only word there is.
        """
        entity_id = event.data[ATTR_ENTITY_ID]

        new_state = event.data["new_state"]
        if new_state is None:
            if er.async_get(self._hass).async_get(entity_id) is None:
                self._async_forget(entity_id)

            return

        if new_state.state in self._moving.get(entity_id, ()):
            # Spook's own doing, which is neither somebody changing their mind
            # nor an automation coming back.
            return

        if (held := self._held.get(entity_id)) is None:
            return

        if new_state.state != held.restore_to:
            self._async_try_again(entity_id, held, new_state.state)
            return

        self._async_forget(entity_id)

    @callback
    def _async_try_again(self, entity_id: str, held: _Held, state: str) -> None:
        """Put back an automation that was away when its time came.

        Its call found nothing to change and left the record alone, so this is
        where it gets its second chance: the automation is back, and it is
        still owed a putting-back.
        """
        if state == STATE_UNAVAILABLE or held.until > dt_util.utcnow():
            return

        # Handed to the loop rather than started here and now, so that
        # unloading in this same breath is seen before anything is changed.
        self._hass.async_create_task(
            self._async_restore(entity_id, held),
            eager_start=False,
        )

    @callback
    def _async_cancel_timer(self, entity_id: str) -> None:
        """Drop the pending wait for one automation, if there is one."""
        if (timer := self._timers.pop(entity_id, None)) is not None:
            timer()

    async def _async_save(self) -> None:
        """Write down what is being held."""
        await self._store.async_save(
            {
                entity_id: {"until": held.until.isoformat(), "state": held.state}
                for entity_id, held in self._held.items()
            }
        )


@callback
def async_get_timed_states(hass: HomeAssistant) -> TimedStates:
    """Return the shared register."""
    return hass.data[DATA_TIMED_STATES]


async def async_setup_timed_states(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Start keeping track of what is held, and return the way to stop."""
    timed_states = hass.data[DATA_TIMED_STATES] = TimedStates(hass)
    stop = await timed_states.async_start()

    @callback
    def _unload() -> None:
        """Stop, and take the register with it.

        Leaving a stopped register behind would hand the next thing that asks
        one that no longer keeps time.
        """
        stop()
        hass.data.pop(DATA_TIMED_STATES, None)

    return _unload
