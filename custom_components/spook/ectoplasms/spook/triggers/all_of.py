"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, trigger as trigger_helper
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
CONF_WITHIN = "within"

# One trigger is not a set of things happening together, it is a trigger. Two
# is the smallest thing this can say something about.
_MINIMUM_TRIGGERS = 2

# What gets lifted out of the trigger that completed the set and put at the top
# of the payload, so `trigger.to_state` and friends mean here what they mean
# everywhere else. It is also what carries the person through: an automation
# starts a fresh context, so a condition asking who set the run going reads
# them off `trigger.to_state`.
#
# An allowlist on purpose. A nested payload also carries `id`, `idx`,
# `platform` and `description`, and what is handed to `run_action` overrides
# those, so merging one wholesale would replace the automation's own
# `trigger.id` and break every `choose` keyed on it.
_CARRIED_FROM_THE_LAST = ("entity_id", "from_state", "to_state", "event")


def _window(value: Any) -> timedelta:
    """Validate the window, and refuse one nothing can happen inside."""
    within = cv.positive_time_period(value)
    if within <= timedelta(0):
        message = "The window must be longer than zero"
        raise vol.Invalid(message)
    return within


_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_TRIGGERS): cv.TRIGGER_SCHEMA,
            vol.Required(CONF_WITHIN): _window,
        },
    }
)


class _AllOfWatcher:
    """Listens to every trigger at once and reports when the set is complete.

    No timers and nothing to arm. Each trigger's last firing is remembered
    with the moment it happened, anything that has fallen out of the window is
    forgotten as it goes, and the only question left is whether what remains
    covers all of them.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        triggers: list[ConfigType],
        within: timedelta,
        on_complete: Callable[
            [list[dict[str, Any]], timedelta, dict[str, Any], Context | None], None
        ],
    ) -> None:
        """Initialize the watcher."""
        self._hass = hass
        self._triggers = triggers
        self._within = within
        self._on_complete = on_complete

        self._seen: dict[int, tuple[datetime, dict[str, Any]]] = {}
        self._unsubs: list[CALLBACK_TYPE] = []

        # Stopping is synchronous and attaching is not, so an attach can be
        # suspended while this is set. See `async_stop`.
        self._stopped = False

    async def async_start(self) -> CALLBACK_TYPE:
        """Attach every trigger, and refuse the lot if one will not go on.

        All of them stay attached for the life of the trigger. There is no
        order to keep, so there is nothing to be gained by listening to them
        one at a time, and a trigger that fires while its neighbours are still
        being attached is counted rather than lost.
        """
        for index in range(len(self._triggers)):
            await self._async_attach(index)

            if self._stopped:
                # Stopped while that was suspended, the same window every
                # attach in Spook has. `_async_attach` has already let go of
                # what it took.
                return self.async_stop

        if len(self._unsubs) != len(self._triggers):
            # One missing trigger means the set can never be complete, so this
            # can never fire. Raising is what gets the automation marked
            # unavailable instead of leaving it looking healthy and silent.
            self.async_stop()
            msg = "Could not attach every trigger of an all-of trigger"
            raise HomeAssistantError(msg)

        return self.async_stop

    async def _async_attach(self, index: int) -> None:
        """Attach one of the triggers and listen for it."""

        async def _fired(
            variables: dict[str, Any] | None = None,
            context: Context | None = None,
        ) -> None:
            """Hand this firing over, saying which of the triggers it was.

            A closure rather than a callable object holding the index. Home
            Assistant decides whether to await an action by inspecting it, and
            an instance with an async `__call__` is not recognised as
            awaitable: the coroutine is created, dropped, and nothing is ever
            counted.
            """
            self._async_one_fired(index, variables, context)

        unsub = await async_attach_nested(
            self._hass,
            [self._triggers[index]],
            _fired,
            f"trigger {index + 1} of an all-of trigger",
            "so its set can never be complete",
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
        index: int,
        variables: dict[str, Any] | None,
        context: Context | None,
    ) -> None:
        """Count one firing, and report if that completed the set.

        Nothing here suspends, so there is no lock: two triggers firing at the
        same moment cannot interleave halfway through this.
        """
        if self._stopped:
            return

        now = dt_util.utcnow()
        payload = (variables or {}).get("trigger", {})

        # The newest firing of a trigger replaces its older one. It did happen
        # again, and the question this answers is whether all of them have
        # happened recently.
        self._seen[index] = (now, payload)

        # What fired longer ago than the window is no longer part of what is
        # happening now. Dropped one at a time rather than the whole lot at
        # once, so two triggers that fired a moment ago still count towards a
        # set that a third completes later.
        cutoff = now - self._within
        self._seen = {
            seen_index: seen
            for seen_index, seen in self._seen.items()
            if seen[0] >= cutoff
        }

        if len(self._seen) < len(self._triggers):
            return

        collected = [self._seen[position][1] for position in range(len(self._triggers))]
        span = now - min(when for when, _ in self._seen.values())

        # Cleared, so the set has to happen again in full. Left standing, the
        # next firing of any one of them would complete the same set over and
        # over, and the trigger would go off on every event instead of once
        # for the thing it was watching for.
        self._seen.clear()

        self._on_complete(collected, span, payload, context)

    @callback
    def async_stop(self) -> None:
        """Detach everything, and refuse to attach any more.

        Stopping is synchronous while attaching is not, so an attach can be
        suspended inside `async_initialize_triggers` at this very moment.
        Whatever that takes afterwards would have nobody left to detach it, so
        the flag tells it to let go of what it just took.
        """
        self._stopped = True

        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._seen.clear()


class SpookTrigger(Trigger):
    """Spook trigger that fires when several things have all happened.

    Home Assistant cannot say "and" over time. Its triggers are a list of
    things any one of which sets an automation off, and `for` covers a single
    state holding still. "These three things have all happened in the last five
    minutes, in whatever order" is not expressible, and written out by hand it
    takes a helper entity per thing and an automation to set each one.

    `spook.sequence` already covers the case where the order matters. The
    difference here is that it does not.
    """

    trigger = "all_of"

    _triggers: list[ConfigType]
    _within: timedelta

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config."""
        shaped: ConfigType = _TRIGGER_SCHEMA(config)
        options = shaped[CONF_OPTIONS]

        if len(options[CONF_TRIGGERS]) < _MINIMUM_TRIGGERS:
            msg = (
                f"An all-of trigger needs at least {_MINIMUM_TRIGGERS} triggers "
                f"to have anything to combine, and this one has "
                f"{len(options[CONF_TRIGGERS])}."
            )
            raise vol.Invalid(msg)

        options[CONF_TRIGGERS] = await trigger_helper.async_validate_trigger_config(
            hass, options[CONF_TRIGGERS]
        )

        return shaped

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        options: dict[str, Any] = config.options or {}
        self._triggers = options[CONF_TRIGGERS]
        self._within = options[CONF_WITHIN]

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def completed(
            triggers: list[dict[str, Any]],
            span: timedelta,
            last: dict[str, Any],
            context: Context | None,
        ) -> None:
            """Run the action, the set having come together."""
            description = last.get("description", "the last of them")

            run_action(
                {
                    **{key: last[key] for key in _CARRIED_FROM_THE_LAST if key in last},
                    "triggers": triggers,
                    "within": self._within,
                    "span": span,
                },
                f"{description}, completing a set of {len(self._triggers)}",
                context,
            )

        watcher = _AllOfWatcher(self._hass, self._triggers, self._within, completed)
        return await watcher.async_start()
