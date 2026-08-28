"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, trigger as trigger_helper
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.trigger import Trigger

from ....trigger_nesting import async_attach_nested

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

CONF_ARM = "arm"
CONF_EXPECT = "expect"
CONF_WITHIN = "within"

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_ARM): cv.TRIGGER_SCHEMA,
            vol.Required(CONF_EXPECT): cv.TRIGGER_SCHEMA,
            vol.Required(CONF_WITHIN): cv.positive_time_period,
        },
    }
)


@dataclass(frozen=True, slots=True)
class _Watch:
    """What to wait for, and how long to give it."""

    arm: list[ConfigType]
    expect: list[ConfigType]
    within: timedelta


@dataclass(slots=True)
class _Armed:
    """One spell of waiting, and the clock running on it.

    Together because they end together, and because the deadline callback
    checks whether this is still the spell it was set for by identity.
    """

    by: dict[str, Any]
    unsub_deadline: CALLBACK_TYPE | None = None


class _Watchdog:
    """Starts a clock when something happens, and barks if nothing follows.

    Armed or not, and nothing in between. Arming again while already armed
    restarts the clock rather than starting a second one: the arming event is
    what the wait is measured from, so the latest one is the one that counts.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        watch: _Watch,
        on_bark: Callable[[dict[str, Any]], None],
    ) -> None:
        """Initialize the watchdog."""
        self._hass = hass
        self._watch = watch
        self._on_bark = on_bark

        self._armed: _Armed | None = None
        self._unsubs: list[CALLBACK_TYPE] = []

        # Arming, the expected thing arriving and the deadline passing all move
        # the same watch, and arming suspends. One at a time.
        self._lock = asyncio.Lock()
        self._stopped = False

    async def async_start(self) -> CALLBACK_TYPE:
        """Listen for both halves, and hand back the way to stop."""
        for configs, action, name in (
            (self._watch.arm, self._async_armed, "the arming triggers"),
            (self._watch.expect, self._async_expected, "the expected triggers"),
        ):
            unsub = await async_attach_nested(
                self._hass, configs, action, f"{name} of a watchdog trigger"
            )

            if unsub is None:
                # Half a watchdog is not a watchdog: without the arming half it
                # never starts, and without the other half it always barks.
                # Refusing is what gets the automation marked unavailable
                # rather than leaving it looking healthy.
                self.async_stop()
                msg = f"Could not attach {name} of a watchdog trigger"
                raise HomeAssistantError(msg)

            self._unsubs.append(unsub)

        return self.async_stop

    @callback
    def async_stop(self) -> None:
        """Stop listening, and drop the clock."""
        self._stopped = True

        self._async_disarm()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    async def _async_armed(
        self,
        variables: dict[str, Any] | None = None,
        _context: Context | None = None,
    ) -> None:
        """Something worth watching for happened. Start the clock."""
        async with self._lock:
            if self._stopped:
                return

            self._async_disarm()
            self._armed = _Armed(by=(variables or {}).get("trigger", {}))
            self._async_start_deadline()

    async def _async_expected(
        self,
        _variables: dict[str, Any] | None = None,
        _context: Context | None = None,
    ) -> None:
        """Stand down, what was being waited for arrived."""
        async with self._lock:
            if self._stopped or self._armed is None:
                # Not armed, so this is just something happening.
                return

            self._async_disarm()

    @callback
    def _async_start_deadline(self) -> None:
        """Give it until the deadline, and bark if it gets there.

        The deadline belongs to the arming that set it. Arming again replaces
        it, and a callback that was already on its way when that happened has
        nothing left to say.
        """
        armed = self._armed
        if armed is None:
            return

        async def _due(_now: datetime) -> None:
            """Bark, nothing having arrived in time."""
            async with self._lock:
                if self._stopped or self._armed is not armed:
                    return

                armed.unsub_deadline = None
                self._async_disarm()
                self._on_bark(armed.by)

        armed.unsub_deadline = async_call_later(
            self._hass, self._watch.within.total_seconds(), _due
        )

    @callback
    def _async_disarm(self) -> None:
        """Stop waiting, whatever the reason.

        Dropping the clock first, because forgetting the spell would otherwise
        lose the handle to it and leave a timer behind.
        """
        self._async_drop_deadline()
        self._armed = None

    @callback
    def _async_drop_deadline(self) -> None:
        """Drop the clock, if one is running."""
        if self._armed is not None and self._armed.unsub_deadline is not None:
            self._armed.unsub_deadline()
            self._armed.unsub_deadline = None


class SpookTrigger(Trigger):
    """Spook trigger that fires when something expected does not happen.

    Every trigger Home Assistant has fires because something happened. The
    interesting failures are the other kind: the back door opened and nobody
    walked into the hall, the washing machine started and never finished, the
    nightly backup began and never reported in.

    Written by hand that is a helper entity, a timer, and two automations to
    keep them in step. Here it is one trigger: arm on this, expect that,
    within so long.
    """

    trigger = "watchdog"

    _watch: _Watch

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config, nested triggers and all."""
        shaped: ConfigType = _TRIGGER_SCHEMA(config)
        options = shaped[CONF_OPTIONS]

        if options[CONF_WITHIN].total_seconds() <= 0:
            msg = (
                "A watchdog with no time to wait barks the moment it is armed, "
                "which is a trigger on the arming half alone."
            )
            raise vol.Invalid(msg)

        for key in (CONF_ARM, CONF_EXPECT):
            options[key] = await trigger_helper.async_validate_trigger_config(
                hass, options[key]
            )

        return shaped

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        options: dict[str, Any] = config.options or {}
        self._watch = _Watch(
            arm=options[CONF_ARM],
            expect=options[CONF_EXPECT],
            within=options[CONF_WITHIN],
        )

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def bark(armed_by: dict[str, Any]) -> None:
            """Run the action, the wait having run out.

            No context handed over. A watchdog fires because nothing happened,
            at a moment a clock came round, and nobody makes a clock come
            round. Whoever armed it is in `trigger.armed_by` for an automation
            that wants to say so itself.
            """
            description = armed_by.get("description", "something")

            run_action(
                {"armed_by": armed_by, "within": self._watch.within},
                f"nothing followed {description} within {self._watch.within}",
            )

        watchdog = _Watchdog(self._hass, self._watch, bark)
        return await watchdog.async_start()
