"""Spook - Your homie."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from lru import LRU

from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime, timedelta

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant

DATA_RUN_HISTORY: HassKey[RunHistory] = HassKey("spook_run_history")

# How many automations are followed at once. Whichever ran least recently is
# dropped, which is the right one to lose: nobody asks about the rate of
# something that has stopped running.
TRACKED_ENTITIES = 256

# How many run times are kept for each of them. This is the ceiling on what a
# quota can ask for, since answering "have there been N runs" needs the Nth
# most recent one to still be there.
MAX_RUNS_REMEMBERED = 64

# One more than that is actually kept, as headroom for a caller that is itself
# already in here: without the spare it would push the oldest of the runs it is
# asking about out of reach, and a limit of 64 could then only ever see 63.
_RUNS_KEPT = MAX_RUNS_REMEMBERED + 1


class RunHistory:
    """Remembers when automations last ran.

    Home Assistant records only the most recent run, on
    ``this.attributes.last_triggered``, which answers "how long ago" but not
    "how many".

    Automations only, and that is a decision rather than an oversight.
    `EVENT_AUTOMATION_TRIGGERED` fires once a run is really happening: one
    whose conditions turned it down does not announce itself, so a blocked run
    costs nothing. Scripts have no equivalent. `EVENT_SCRIPT_STARTED` fires
    before the engine decides whether the run is allowed at all, so a call
    turned down by `mode: single` announces itself just the same, and counting
    those would spend an allowance on runs that never happened.

    Listening starts when Spook does, so the history is already there by the
    time anything asks.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the history."""
        self._hass = hass
        self._runs: LRU = LRU(TRACKED_ENTITIES)
        self._unsubs: list[CALLBACK_TYPE] = []

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Start listening, and return the way to stop."""
        if not self._unsubs:
            self._unsubs = [
                self._hass.bus.async_listen(EVENT_AUTOMATION_TRIGGERED, self._async_ran)
            ]
        return self.async_stop

    @callback
    def async_stop(self) -> None:
        """Stop listening and let go of what was remembered."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._runs.clear()

    @callback
    def async_runs_within(
        self,
        entity_id: str,
        period: timedelta,
        ignoring: str | None = None,
    ) -> int:
        """Return how many times this one ran within the given period.

        ``ignoring`` leaves out the most recent run under that context, which
        is how a caller excludes the run it is part of. An automation
        announces itself only once its conditions have passed, so a condition
        gating one of those is not in here yet and this changes nothing. A
        condition sitting inside the actions is, and should not be made to
        count the run it is part of.

        The most recent one, and only that one. Contexts are inherited down a
        chain, so several runs can share one, and dropping every match would
        leave an allowance unspent.
        """
        since = dt_util.utcnow() - period
        within = 0
        own_run_skipped = False

        for when, context_id in self._async_runs(entity_id):
            # A run exactly a period old has served its time, which is how
            # `spook.cooldown` reads its own boundary: expired at `elapsed >=
            # duration` rather than one instant later.
            if when <= since:
                continue

            if not own_run_skipped and context_id == ignoring:
                own_run_skipped = True
                continue

            within += 1

        return within

    @callback
    def _async_runs(self, entity_id: str) -> Sequence[tuple[datetime, str]]:
        """Return when this one ran and under which context, most recent first."""
        return self._runs.get(entity_id) or ()  # type: ignore[no-any-return]

    @callback
    def _async_ran(self, event: Event) -> None:
        """Note that something just ran."""
        if not (entity_id := event.data.get(ATTR_ENTITY_ID)):
            return

        if (runs := self._runs.get(entity_id)) is None:
            runs = deque(maxlen=_RUNS_KEPT)
            self._runs[entity_id] = runs

        # Newest first, so the oldest is the one a full deque drops.
        runs.appendleft((dt_util.utcnow(), event.context.id))


@callback
def async_get_run_history(hass: HomeAssistant) -> RunHistory:
    """Return the shared history, starting it if this is the first ask."""
    if (history := hass.data.get(DATA_RUN_HISTORY)) is None:
        history = RunHistory(hass)
        hass.data[DATA_RUN_HISTORY] = history
        history.async_start()
    return history


@callback
def async_setup_run_history(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Start remembering when things ran, and return the way to stop."""
    return async_get_run_history(hass).async_start()
