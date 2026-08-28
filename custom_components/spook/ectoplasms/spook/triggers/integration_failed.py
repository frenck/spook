"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntryState,
)
from homeassistant.const import CONF_FOR, CONF_OPTIONS
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.trigger import Trigger
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry, ConfigEntryChange
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

CONF_ENTRY_ID = "entry_id"

# The states that mean setting up went wrong.
FAILED_STATES = frozenset(
    {
        ConfigEntryState.SETUP_ERROR,
        ConfigEntryState.SETUP_RETRY,
        ConfigEntryState.MIGRATION_ERROR,
        ConfigEntryState.FAILED_UNLOAD,
    }
)

# Not a failure, but not a recovery either. An entry that keeps retrying passes
# through this on every attempt, so treating it as recovery would restart the
# clock every time and nothing would ever be reported as broken for long.
IN_BETWEEN_STATES = frozenset(
    {
        ConfigEntryState.SETUP_IN_PROGRESS,
        ConfigEntryState.UNLOAD_IN_PROGRESS,
    }
)


def _broken_period(value: Any) -> timedelta:
    """Validate the duration, and refuse one that can never elapse.

    Zero would put the deadline in the past, so the trigger would load and
    then never fire, which is worse than saying no.
    """
    duration = cv.positive_time_period(value)
    if duration <= timedelta(0):
        message = "The duration must be longer than zero"
        raise vol.Invalid(message)
    return duration


_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_FOR): _broken_period,
            vol.Optional(CONF_ENTRY_ID): vol.All(cv.ensure_list, [cv.string]),
        },
    }
)


@dataclass
class _Trouble:
    """What is known about one config entry's current spell of trouble.

    The state and reason are kept up to date on every failed attempt, because
    the entry may well be mid-retry by the time the wait runs out, and
    `setup_in_progress` with nothing attached is no answer to what went wrong.
    """

    state: ConfigEntryState
    reason: str | None
    wait: CALLBACK_TYPE | None = None
    reported: bool = False


# Everything here is driven by the dispatcher or by a timer, so there is
# nothing public to count.
# pylint: disable-next=too-few-public-methods
class _FailedEntryTracker:
    """Follow config entries and report the ones that stay broken.

    One dispatcher subscription covers every entry, including ones added
    later: Home Assistant sends `SIGNAL_CONFIG_ENTRY_CHANGED` on every state
    change a config entry makes.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        duration: timedelta,
        entry_ids: set[str] | None,
        on_failed: Callable[[ConfigEntry, ConfigEntryState, str | None], None],
    ) -> None:
        """Initialize the tracker."""
        self._hass = hass
        self._duration = duration
        self._entry_ids = entry_ids
        self._on_failed = on_failed
        self._troubles: dict[str, _Trouble] = {}
        self._unsub_signal: CALLBACK_TYPE | None = None

    @callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Start watching, and return the way to stop."""
        # Entries that are already broken are picked up too. One stuck in
        # `SETUP_ERROR` never announces itself again, so waiting for a change
        # would mean never hearing about the entries that broke before this
        # automation loaded, which are the ones worth hearing about.
        for entry in self._hass.config_entries.async_entries():
            if entry.state in FAILED_STATES and self._is_watched(entry):
                self._note_trouble(entry)

        self._unsub_signal = async_dispatcher_connect(
            self._hass, SIGNAL_CONFIG_ENTRY_CHANGED, self._entry_changed
        )
        return self._unsubscribe

    def _is_watched(self, entry: ConfigEntry) -> bool:
        """Return whether this entry is one of the ones asked about."""
        return self._entry_ids is None or entry.entry_id in self._entry_ids

    @callback
    def _entry_changed(
        self,
        _change: ConfigEntryChange,
        entry: ConfigEntry,
    ) -> None:
        """Follow one config entry through its states.

        Removal needs no case of its own: an entry passes through
        `not_loaded` on its way out, which is already a recovery as far as
        this is concerned, so the wait is dropped there.
        """
        if not self._is_watched(entry):
            return

        if entry.state in FAILED_STATES:
            self._note_trouble(entry)
        elif entry.state not in IN_BETWEEN_STATES:
            self._forget(entry.entry_id)

    @callback
    def _note_trouble(self, entry: ConfigEntry) -> None:
        """Record this failure, and start counting if nothing is counting yet.

        Already reported counts as counted: one report per spell of trouble.
        A failing entry announces itself on every retry, and starting a fresh
        wait on each of those would turn this into a quarter-hourly nag until
        somebody got round to fixing it.
        """
        if (trouble := self._troubles.get(entry.entry_id)) is None:
            trouble = _Trouble(entry.state, entry.reason)
            self._troubles[entry.entry_id] = trouble
        else:
            trouble.state = entry.state
            trouble.reason = entry.reason

        if trouble.wait is not None or trouble.reported:
            return

        trouble.wait = async_track_point_in_time(
            self._hass,
            partial(self._still_broken, entry),
            dt_util.utcnow() + self._duration,
        )

    @callback
    def _still_broken(self, entry: ConfigEntry, _fired_at: datetime) -> None:
        """Report an entry that has been unable to set up all this time."""
        if (trouble := self._troubles.get(entry.entry_id)) is None:
            return

        trouble.wait = None
        trouble.reported = True
        self._on_failed(entry, trouble.state, trouble.reason)

    @callback
    def _forget(self, entry_id: str) -> None:
        """Drop everything held about one entry: it is out of trouble."""
        if (trouble := self._troubles.pop(entry_id, None)) is None:
            return

        if trouble.wait is not None:
            trouble.wait()

    @callback
    def _unsubscribe(self) -> None:
        """Stop watching, and drop every pending wait."""
        if self._unsub_signal is not None:
            self._unsub_signal()
            self._unsub_signal = None

        for entry_id in list(self._troubles):
            self._forget(entry_id)


class SpookTrigger(Trigger):
    """Spook trigger that fires when an integration stays broken.

    Home Assistant retries a config entry that fails to set up, with a backoff
    that tops out at ten minutes. A device that is off overnight therefore
    lands in the failed state dozens of times before morning, so a trigger
    that fired on every one of those would be useless. This one waits: it
    fires only once an entry has been unable to set up for the whole duration,
    which is also long enough for the ordinary failures at start-up to sort
    themselves out.
    """

    trigger = "integration_failed"

    _duration: timedelta
    _entry_ids: set[str] | None

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
        entry_ids = options.get(CONF_ENTRY_ID)
        self._entry_ids = set(entry_ids) if entry_ids else None

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def entry_stayed_broken(
            entry: ConfigEntry,
            state: ConfigEntryState,
            reason: str | None,
        ) -> None:
            """Run the action for the entry that could not set itself up."""
            run_action(
                {
                    "entry_id": entry.entry_id,
                    "domain": entry.domain,
                    "title": entry.title,
                    "state": state.value,
                    "reason": reason,
                    "for": self._duration,
                },
                f"{entry.title} ({entry.domain}) failed for {self._duration}",
            )

        tracker = _FailedEntryTracker(
            self._hass, self._duration, self._entry_ids, entry_stayed_broken
        )
        return tracker.async_setup()
