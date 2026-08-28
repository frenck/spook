"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_CONDITION
from homeassistant.core import callback
from homeassistant.exceptions import ConditionError
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from datetime import datetime

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.condition import ConditionChecker
    from homeassistant.helpers.typing import ConfigType

# How often a condition is asked again regardless of anything happening.
#
# Conditions in Home Assistant are asked, not announced, so something has to
# prompt the asking. Most of them name the entities they depend on and those
# are watched directly, but a template condition names none that can be read
# off the config, and a plain time or sun condition has none to name. Those
# turn true on their own account, so they are asked on a timer as well.
#
# Which is a polling interval, not a bound on how late a turn is noticed: a
# condition that turns true and false again between two ticks is missed.
BACKSTOP = timedelta(seconds=30)

# Conditions that answer about the run they are asked in: which trigger fired,
# which automation is running, who pressed the button. Watching is asking over
# and over outside any run at all, so there is nothing for them to answer and
# they say no every time. Quietly, which is why they are refused instead.
CONTEXT_DEPENDENT = frozenset(
    {
        "trigger",
        "spook.cooldown",
        "spook.not_triggered_by_user",
        "spook.quota",
        "spook.triggered_by_automation",
        "spook.triggered_by_user",
    }
)


def _condition_types(config: Any) -> Iterator[str]:
    """Yield the type of every condition in a config, however deeply nested."""
    if isinstance(config, dict):
        if isinstance(kind := config.get(CONF_CONDITION), str):
            yield kind
        for value in config.values():
            yield from _condition_types(value)
    elif isinstance(config, list):
        for item in config:
            yield from _condition_types(item)


class ConditionWatcher:
    """Watches a condition and reports when it turns true.

    Only the turn. A condition that is already true when watching starts is
    not a change, and callers that care about the current value ask for it.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        checker: ConditionChecker,
        entity_ids: set[str],
        on_met: Callable[[], None],
    ) -> None:
        """Initialize the watcher."""
        self._hass = hass
        self._checker = checker
        self._entity_ids = entity_ids
        self._on_met = on_met
        self._met = False
        self._unsubs: list[CALLBACK_TYPE] = []

    @property
    def met(self) -> bool:
        """Return what the condition said when it was last asked."""
        return self._met

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Ask once, start watching, and return the way to stop."""
        self._met = self._async_ask()

        if self._entity_ids:
            self._unsubs.append(
                async_track_state_change_event(
                    self._hass, list(self._entity_ids), self._async_entity_changed
                )
            )

        # Always, even when there are entities to watch: a condition can be an
        # `and` of a state and a template, and only half of that announces
        # itself.
        self._unsubs.append(
            async_track_time_interval(self._hass, self._async_look_again, BACKSTOP)
        )

        return self.async_stop

    @callback
    def async_stop(self) -> None:
        """Stop watching."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._checker.async_unload()

    @callback
    def _async_ask(self) -> bool:
        """Ask the condition, treating a refusal to answer as a no.

        A condition may return ``None`` when it cannot tell, and may raise a
        `ConditionError` for the same reason: a template that errored, an
        entity that has gone. Neither is true, and neither is worth taking the
        watcher down for. Anything else is a real fault and is left to travel.
        """
        try:
            return self._checker.async_check() is True
        except ConditionError:
            return False

    @callback
    def _async_entity_changed(self, _event: Event) -> None:
        """Ask again, because something the condition depends on moved."""
        self._async_look()

    @callback
    def _async_look_again(self, _now: datetime) -> None:
        """Ask again, because the backstop came round."""
        self._async_look()

    @callback
    def _async_look(self) -> None:
        """Ask again, and report only a turn from false to true."""
        met = self._async_ask()
        if met == self._met:
            return

        self._met = met
        if met:
            self._on_met()


async def async_validate_condition(
    hass: HomeAssistant,
    config: ConfigType,
) -> ConfigType:
    """Put a condition config through both halves of Home Assistant's checks.

    Not politeness: the schema turns a template into a `Template` and a single
    entity into a list, and a checker built from the shorthand people actually
    write raises on every check rather than answering. Doing it up front also
    means a bad condition is refused when the automation loads instead of
    failing silently later.

    Has to run in the event loop, because validating a template does.
    """
    validated = await condition.async_validate_condition_config(
        hass, cv.CONDITION_SCHEMA(config)
    )

    if unwatchable := CONTEXT_DEPENDENT.intersection(_condition_types(validated)):
        msg = (
            "Cannot watch a condition that asks about the run it is in: "
            f"{', '.join(sorted(unwatchable))}. There is no run here to ask about, "
            "so it would never be true."
        )
        raise vol.Invalid(msg)

    return validated


async def async_condition_watcher(
    hass: HomeAssistant,
    validated: ConfigType,
    on_met: Callable[[], None],
) -> ConditionWatcher:
    """Build a watcher for an already validated condition, ready to start."""
    checker = await condition.async_from_config(hass, validated)
    return ConditionWatcher(
        hass, checker, condition.async_extract_entities(validated), on_met
    )
