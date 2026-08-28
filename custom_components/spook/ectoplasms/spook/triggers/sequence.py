"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS, CONF_TIMEOUT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, trigger as trigger_helper
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.trigger import Trigger
from homeassistant.util import dt as dt_util

from ....const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime, timedelta

    from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

CONF_STEPS = "steps"
CONF_RESET = "reset"

# One trigger is not an order, it is a trigger. Two is the smallest thing this
# can say something about.
_MINIMUM_STEPS = 2

# What gets lifted out of the step that completed the sequence and put at the
# top of the payload, so `trigger.to_state` and friends mean here what they
# mean everywhere else. It is also what carries the user through: an automation
# starts a fresh context, so a condition asking who set the run going reads the
# person off `trigger.to_state`.
#
# An allowlist on purpose. A step's payload also carries `id`, `idx`,
# `platform` and `description`, and what is handed to `run_action` overrides
# those, so merging a step wholesale would replace the automation's own
# `trigger.id` with the step's and break every `choose` keyed on it.
_CARRIED_FROM_LAST_STEP = ("entity_id", "from_state", "to_state", "event")

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_STEPS): cv.TRIGGER_SCHEMA,
            vol.Optional(CONF_TIMEOUT): cv.positive_time_period,
            vol.Optional(CONF_RESET): cv.TRIGGER_SCHEMA,
        },
    }
)


@callback
def _log(level: int, message: str, **kwargs: Any) -> None:
    """Take the log line Home Assistant writes about a nested trigger.

    `async_initialize_triggers` insists on somewhere to write, and what it
    writes is about a trigger the user did not attach themselves, so it goes
    to Spook's logger rather than an automation's.
    """
    LOGGER.log(level, "Spook sequence trigger: %s", message, **kwargs)


@dataclass(frozen=True, slots=True)
class _Sequence:
    """What to wait for. Fixed for the life of the trigger."""

    steps: list[ConfigType]
    reset: list[ConfigType]
    timeout: timedelta | None


@dataclass(slots=True)
class _Run:
    """Where one pass through the sequence has got to.

    Together in one place because they are abandoned together: a reset or a
    deadline throws the whole thing away rather than picking fields off it.
    The deadline belongs to the run for the same reason.
    """

    armed: int = 0
    collected: list[dict[str, Any]] = field(default_factory=list)
    started: datetime | None = None
    unsub_timeout: CALLBACK_TYPE | None = None


class _SequenceWatcher:
    """Arms one step at a time and reports when the last one lands.

    Only the step it is waiting for is attached, which is what makes the order
    mean anything: the second trigger firing before the first has fired is not
    a sequence, and nothing is listening for it at that point.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        sequence: _Sequence,
        on_complete: Callable[[list[dict[str, Any]], timedelta, Context | None], None],
    ) -> None:
        """Initialize the watcher."""
        self._hass = hass
        self._sequence = sequence
        self._on_complete = on_complete

        self._run = _Run()
        self._unsub_step: CALLBACK_TYPE | None = None
        self._unsub_reset: CALLBACK_TYPE | None = None

        # A step landing, a reset firing and a deadline passing all move the
        # same run, and all of them suspend while they re-arm. One at a time,
        # or two of them interleave and the run ends up half moved.
        self._lock = asyncio.Lock()

    async def async_start(self) -> CALLBACK_TYPE:
        """Arm the first step, and the reset triggers if there are any.

        The reset triggers stay attached for as long as this watcher lives,
        rather than only during a run. Attaching them is asynchronous, so
        arming them per run would leave a window where a reset that arrives
        early is missed, and ignoring them while idle costs nothing.
        """
        if self._sequence.reset:
            self._unsub_reset = await trigger_helper.async_initialize_triggers(
                self._hass,
                self._sequence.reset,
                self._async_reset_fired,
                DOMAIN,
                "sequence reset",
                _log,
            )

        await self._async_arm(0)
        return self.async_stop

    @callback
    def async_stop(self) -> None:
        """Detach everything."""
        self._async_disarm_step()
        self._async_drop_timeout()

        if self._unsub_reset is not None:
            self._unsub_reset()
            self._unsub_reset = None

    async def _async_arm(self, index: int) -> None:
        """Attach the step at `index` and wait for it."""
        self._run.armed = index

        async def _fired(
            variables: dict[str, Any] | None = None,
            context: Context | None = None,
        ) -> None:
            """Hand this step over, saying which step it was.

            A closure rather than a callable object holding the index. Home
            Assistant decides whether to await an action by inspecting it, and
            an instance with an async `__call__` is not recognised as
            awaitable: the coroutine is created, dropped, and the sequence
            never advances. Measured, at the cost of an afternoon.
            """
            await self._async_step_fired(index, variables, context)

        self._unsub_step = await trigger_helper.async_initialize_triggers(
            self._hass,
            [self._sequence.steps[index]],
            _fired,
            DOMAIN,
            f"step {index + 1}",
            _log,
        )

        if self._unsub_step is None:
            # `async_initialize_triggers` hands back nothing when it could not
            # attach anything, having logged why. Say so as well: a sequence
            # stuck on a step it cannot listen for is a trigger that never
            # fires, and that is the failure mode worth being loud about.
            LOGGER.warning(
                "Spook could not attach step %s of a sequence trigger, "
                "so it will not fire",
                index + 1,
            )

    @callback
    def _async_disarm_step(self) -> None:
        """Stop waiting for the currently armed step."""
        if self._unsub_step is not None:
            self._unsub_step()
            self._unsub_step = None

    @callback
    def _async_drop_timeout(self) -> None:
        """Drop the deadline, if one is pending."""
        if self._run.unsub_timeout is not None:
            self._run.unsub_timeout()
            self._run.unsub_timeout = None

    async def _async_step_fired(
        self,
        index: int,
        variables: dict[str, Any] | None,
        context: Context | None,
    ) -> None:
        """Take a step that landed, and either finish or move on."""
        async with self._lock:
            if index != self._run.armed:
                # A firing of a step already left behind, which happens when
                # this had to queue on the lock: a reset or a deadline holds it
                # while it moves the run back to the start, and the step waiting
                # behind them is answering a question nobody is asking any more.
                #
                # Not the double-firing case. Home Assistant starts the action
                # eagerly, so a step detaches itself while the first event is
                # still being handed out, and a second event never reaches it.
                # Measured, after writing the opposite here first.
                return

            self._async_disarm_step()
            self._run.collected.append((variables or {}).get("trigger", {}))

            if index == 0:
                self._run.started = dt_util.utcnow()
                self._async_start_timeout()

            if index + 1 < len(self._sequence.steps):
                await self._async_arm(index + 1)
                return

            collected = self._run.collected
            started = self._run.started or dt_util.utcnow()
            self._async_abandon()
            await self._async_arm(0)

            self._on_complete(collected, dt_util.utcnow() - started, context)

    async def _async_reset_fired(
        self,
        _variables: dict[str, Any] | None = None,
        _context: Context | None = None,
    ) -> None:
        """Abandon a run in progress, because something said to."""
        async with self._lock:
            if self._run.armed == 0 and not self._run.collected:
                # Nothing under way, so nothing to abandon.
                return

            self._async_disarm_step()
            self._async_abandon()
            await self._async_arm(0)

    @callback
    def _async_start_timeout(self) -> None:
        """Put a deadline on the whole run, if one was configured."""
        if self._sequence.timeout is None:
            return

        self._run.unsub_timeout = async_call_later(
            self._hass, self._sequence.timeout.total_seconds(), self._async_timed_out
        )

    async def _async_timed_out(self, _now: datetime) -> None:
        """Give up on the run, the deadline passed."""
        self._run.unsub_timeout = None
        async with self._lock:
            self._async_disarm_step()
            self._async_abandon()
            await self._async_arm(0)

    @callback
    def _async_abandon(self) -> None:
        """Forget the run so far. The caller arms the first step again.

        Dropping the deadline first, because replacing the run would otherwise
        lose the handle to it and leave a timer behind.
        """
        self._async_drop_timeout()
        self._run = _Run()


class SpookTrigger(Trigger):
    """Spook trigger that fires when several triggers happen in order.

    Home Assistant can fire on one thing happening. It cannot fire on one
    thing happening after another, which is most of what a house does: the
    door opened and then somebody moved in the hall, the washing machine
    started and then went quiet. Written out by hand that needs a helper
    entity per step and an automation to set each one.

    Only the step being waited for is attached, so a later trigger firing
    before an earlier one is not a match, and neither is the same step firing
    twice.
    """

    trigger = "sequence"

    _sequence: _Sequence

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config, nested triggers and all.

        Both halves, the same as a condition needs: the schema turns what the
        selector sends into a list of trigger configs, and
        `async_validate_trigger_config` is what checks each of them against
        the platform it names.
        """
        shaped: ConfigType = _TRIGGER_SCHEMA(config)
        options = shaped[CONF_OPTIONS]

        if len(options[CONF_STEPS]) < _MINIMUM_STEPS:
            msg = (
                f"A sequence needs at least {_MINIMUM_STEPS} steps to be a "
                f"sequence, and this one has {len(options[CONF_STEPS])}."
            )
            raise vol.Invalid(msg)

        options[CONF_STEPS] = await trigger_helper.async_validate_trigger_config(
            hass, options[CONF_STEPS]
        )
        if CONF_RESET in options:
            options[CONF_RESET] = await trigger_helper.async_validate_trigger_config(
                hass, options[CONF_RESET]
            )

        return shaped

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        options: dict[str, Any] = config.options or {}
        self._sequence = _Sequence(
            steps=options[CONF_STEPS],
            reset=options.get(CONF_RESET, []),
            timeout=options.get(CONF_TIMEOUT),
        )

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def completed(
            steps: list[dict[str, Any]],
            duration: timedelta,
            context: Context | None,
        ) -> None:
            """Run the action, the last step having landed."""
            last = steps[-1] if steps else {}
            description = last.get("description", "the last step")

            run_action(
                {
                    **{
                        key: last[key] for key in _CARRIED_FROM_LAST_STEP if key in last
                    },
                    "steps": steps,
                    "duration": duration,
                },
                f"{description}, completing a sequence of {len(self._sequence.steps)}",
                context,
            )

        watcher = _SequenceWatcher(self._hass, self._sequence, completed)
        return await watcher.async_start()
