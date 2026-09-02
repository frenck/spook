"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_FOR, CONF_OPTIONS
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, trigger as trigger_helper
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.trigger import Trigger
from homeassistant.util import dt as dt_util

from ....trigger_nesting import async_attach_nested

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

CONF_TRIGGERS = "triggers"

# What gets lifted out of the last firing of a burst and put at the top of the
# payload, so `trigger.to_state` and friends mean here what they mean
# everywhere else. It is also what carries the person through: an automation
# starts a fresh context, so a condition asking who set the run going reads
# them off `trigger.to_state`.
#
# An allowlist on purpose. A nested payload also carries `id`, `idx`,
# `platform` and `description`, and what is handed to `run_action` overrides
# those, so merging one wholesale would replace the automation's own
# `trigger.id` and break every `choose` keyed on it.
_CARRIED_FROM_THE_LAST = ("entity_id", "from_state", "to_state", "event")


def _a_real_pause(value: Any) -> timedelta:
    """Validate the quiet period, and refuse one nothing could be quieter than.

    Zero would fire on the first thing to happen and collapse nothing at all,
    which is the trigger it was given, only slower.
    """
    duration = cv.positive_time_period(value)
    if duration <= timedelta(0):
        message = "The quiet period must be longer than zero"
        raise vol.Invalid(message)
    return duration


_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_TRIGGERS): cv.TRIGGER_SCHEMA,
            vol.Required(CONF_FOR): _a_real_pause,
        },
    }
)


@dataclass(slots=True)
class _Burst:
    """One run of firings that have not finished arriving yet."""

    started: datetime
    last_at: datetime
    last: dict[str, Any] = field(default_factory=dict)
    context: Context | None = None
    count: int = 1
    unsub: CALLBACK_TYPE | None = None


class _BurstWatcher:
    """Listens to the triggers and reports once they have stopped.

    Only counts are kept, not every payload. A burst has no ceiling: a sensor
    that will not settle can fire hundreds of times, and holding all of that
    to hand over is a memory cost for something nobody reads. The last firing
    is the one worth having.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        triggers: list[ConfigType],
        pause: timedelta,
        on_quiet: Callable[[int, timedelta, dict[str, Any], Context | None], None],
    ) -> None:
        """Initialize the watcher."""
        self._hass = hass
        self._triggers = triggers
        self._pause = pause
        self._on_quiet = on_quiet

        self._burst: _Burst | None = None
        self._unsubs: list[CALLBACK_TYPE] = []

        # Stopping is synchronous and attaching is not, so an attach can be
        # suspended while this is set. See `async_stop`.
        self._stopped = False

    async def async_start(self) -> CALLBACK_TYPE:
        """Attach every trigger, and refuse the lot if one will not go on."""
        for index in range(len(self._triggers)):
            await self._async_attach(index)

            if self._stopped:
                # Stopped while that was suspended, the same window every
                # attach in Spook has. `_async_attach` has already let go of
                # what it took.
                return self.async_stop

        if len(self._unsubs) != len(self._triggers):
            # A trigger that is not listening is one that can never start a
            # burst, so what this reports would be missing the thing somebody
            # asked about. Raising is what gets the automation marked
            # unavailable instead of leaving it looking healthy and silent.
            self.async_stop()
            msg = "Could not attach every trigger of a debounce trigger"
            raise HomeAssistantError(msg)

        return self.async_stop

    async def _async_attach(self, index: int) -> None:
        """Attach one of the triggers and listen for it."""

        async def _fired(
            variables: dict[str, Any] | None = None,
            context: Context | None = None,
        ) -> None:
            """Take one firing.

            A closure rather than a callable object. Home Assistant decides
            whether to await an action by inspecting it, and an instance with
            an async `__call__` is not recognised as awaitable: the coroutine
            is created, dropped, and nothing is ever counted.
            """
            self._async_one_fired(variables, context)

        unsub = await async_attach_nested(
            self._hass,
            [self._triggers[index]],
            _fired,
            f"trigger {index + 1} of a debounce trigger",
            "so what it does will go unnoticed",
        )

        if self._stopped:
            # Stopped while this was suspended. Nobody is holding the handle
            # any more, so let go of it here.
            if unsub is not None:
                unsub()
            return

        if unsub is not None:
            self._unsubs.append(unsub)

    @callback
    def _async_one_fired(
        self,
        variables: dict[str, Any] | None,
        context: Context | None,
    ) -> None:
        """Count one firing and start the wait for quiet over again.

        Nothing here suspends, so there is no lock: two firings at the same
        moment cannot interleave halfway through this.
        """
        if self._stopped:
            return

        now = dt_util.utcnow()
        payload = (variables or {}).get("trigger", {})

        if self._burst is None:
            self._burst = _Burst(started=now, last_at=now)
        else:
            self._burst.count += 1
            self._burst.last_at = now

        self._burst.last = payload
        self._burst.context = context

        self._async_drop_wait()
        self._async_start_wait()

    @callback
    def _async_start_wait(self) -> None:
        """Wait out the quiet period, on the burst that is running now.

        The wait is tied to the burst that set it. A due callback that arrives
        after that burst was reported, or after a fresh one started, is
        answering a question nobody is asking any more.
        """
        if (burst := self._burst) is None:
            return

        @callback
        def _quiet(_now: datetime) -> None:
            """Nothing more arrived, so this burst is over."""
            if self._stopped or self._burst is not burst:
                return

            # Cleared on the burst this belongs to, so it cannot wipe a newer
            # one's handle and leave that timer behind.
            burst.unsub = None
            self._burst = None

            self._on_quiet(
                burst.count,
                burst.last_at - burst.started,
                burst.last,
                burst.context,
            )

        burst.unsub = async_call_later(self._hass, self._pause.total_seconds(), _quiet)

    @callback
    def _async_drop_wait(self) -> None:
        """Drop the pending wait, if there is one."""
        if self._burst is not None and self._burst.unsub is not None:
            self._burst.unsub()
            self._burst.unsub = None

    @callback
    def async_stop(self) -> None:
        """Detach everything, and refuse to attach any more.

        Stopping is synchronous while attaching is not, so an attach can be
        suspended inside `async_initialize_triggers` at this very moment.
        Whatever that takes afterwards would have nobody left to detach it, so
        the flag tells it to let go of what it just took.
        """
        self._stopped = True

        self._async_drop_wait()
        self._burst = None

        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()


class SpookTrigger(Trigger):
    """Spook trigger that fires once something has stopped happening.

    A motion sensor in a hallway does not report motion, it reports motion
    twenty times. A power meter crossing a threshold crosses it back and forth
    for a minute. Acting on the first of those is usually wrong and acting on
    every one of them is always wrong, and what you wanted was to hear about
    it once, after it settled.

    Written out by hand that is a helper entity and a second automation to
    turn it off again, which is the most rebuilt pattern on the forum.

    Not the same as `spook.watchdog`, which is about something that never
    happened at all.
    """

    trigger = "debounce"

    _triggers: list[ConfigType]
    _pause: timedelta

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config."""
        shaped: ConfigType = _TRIGGER_SCHEMA(config)
        options = shaped[CONF_OPTIONS]

        options[CONF_TRIGGERS] = await trigger_helper.async_validate_trigger_config(
            hass, options[CONF_TRIGGERS]
        )

        return shaped

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        options: dict[str, Any] = config.options or {}
        self._triggers = options[CONF_TRIGGERS]
        self._pause = options[CONF_FOR]

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def settled(
            count: int,
            span: timedelta,
            last: dict[str, Any],
            context: Context | None,
        ) -> None:
            """Run the action, the burst having stopped."""
            description = last.get("description", "it")

            run_action(
                {
                    **{key: last[key] for key in _CARRIED_FROM_THE_LAST if key in last},
                    "count": count,
                    "span": span,
                    "for": self._pause,
                },
                f"{description}, having settled after {count} in {span}",
                context,
            )

        watcher = _BurstWatcher(self._hass, self._triggers, self._pause, settled)
        return await watcher.async_start()
