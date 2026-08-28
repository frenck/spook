"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import jinja2
from jinja2 import meta as jinja_meta
import voluptuous as vol

from homeassistant.const import CONF_CONDITION, CONF_CONDITIONS, CONF_OPTIONS
from homeassistant.core import callback
from homeassistant.exceptions import ConditionError
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.template import Template

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from datetime import datetime

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.condition import ConditionChecker
    from homeassistant.helpers.event import EventStateChangedData
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
# and over outside any run at all, so the answer means nothing here. Measured
# with no run: `trigger`, `spook.triggered_by_automation` and
# `spook.triggered_by_user` say no every time, and `spook.cooldown`,
# `spook.quota` and `spook.not_triggered_by_user` say yes every time. Both are
# useless and both are quiet about it, which is why these are refused.
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

# The same trouble a level down. A template condition can be watched, but not
# when it reaches for something only a run provides. Home Assistant fills these
# in while an automation or script runs, and nowhere else.
RUN_SCOPED_NAMES = frozenset({"repeat", "this", "trigger", "wait"})

# The condition types that hold other conditions, as Home Assistant has them.
_NESTING = ("and", "not", "or")

# Bare Jinja, deliberately. Only the shape of a template matters here, not what
# Home Assistant's filters and globals do, and asking Jinja which names a
# template reaches for beats searching the text: `states('sensor.trigger_count')`
# reaches for `states`, not for `trigger`. Verified that none of Home
# Assistant's template extensions add syntax of their own, so this parses
# everything they accept.
_JINJA = jinja2.Environment(
    extensions=("jinja2.ext.loopcontrols", "jinja2.ext.do"),
    autoescape=True,
)


def iter_templates(config: Any) -> Iterator[Template]:
    """Yield every template in a condition config, however deeply nested."""
    if isinstance(config, Template):
        yield config
    elif isinstance(config, dict):
        for value in config.values():
            yield from iter_templates(value)
    elif isinstance(config, list):
        for item in config:
            yield from iter_templates(item)


def _condition_types(config: Any) -> Iterator[str]:
    """Yield the type of every condition in a config.

    Walks the way Home Assistant walks a condition tree: into the `conditions`
    of an `and`, `or` or `not`, and no further. What a condition carries beyond
    that is its own payload, and a payload that happens to hold a `condition`
    key is not a condition.
    """
    for item in config if isinstance(config, list) else [config]:
        if not isinstance(item, dict) or not isinstance(
            kind := item.get(CONF_CONDITION), str
        ):
            continue

        yield kind

        if kind in _NESTING:
            yield from _condition_types(item.get(CONF_CONDITIONS, []))


# Condition types whose every turn arrives as a state change of an entity they
# name, so the change that arrives is the change that turned them.
#
# Which is what makes attribution possible, and its absence is why nothing is
# attributed otherwise. Say a condition is `and` of a state and a template: the
# template can quietly become true, and the next unrelated update to the state
# entity is what notices. Blaming that update, and whoever caused it, for the
# turn would be wrong.
_OBSERVABLE = frozenset({"numeric_state", "state", "zone"})

# Keys that put a turn out of reach of the entities a condition names. A `for`
# turns true when a duration runs out and nothing moves; a `value_template`
# reaches for entities that cannot be read off the config.
_UNOBSERVABLE_KEYS = ("for", "value_template")


def _leaf_announces_every_turn(config: ConfigType) -> bool:
    """Report whether a single condition tells us about all of its turns."""
    if config[CONF_CONDITION] not in _OBSERVABLE:
        return False

    # A `zone` condition keeps its configuration under `options`, so both
    # places have to be looked at.
    options = config.get(CONF_OPTIONS) or {}
    if any(key in config or key in options for key in _UNOBSERVABLE_KEYS):
        return False

    # A `numeric_state` threshold can name an entity, and that entity is not
    # part of what gets extracted, so a change to it goes unnoticed.
    return not any(
        isinstance(config.get(bound) or options.get(bound), str)
        for bound in ("above", "below")
    )


def _announces_every_turn(config: Any) -> bool:
    """Report whether a whole condition tree tells us about all of its turns."""
    for item in config if isinstance(config, list) else [config]:
        if not isinstance(item, dict) or not isinstance(
            kind := item.get(CONF_CONDITION), str
        ):
            return False

        if kind in _NESTING:
            if not _announces_every_turn(item.get(CONF_CONDITIONS, [])):
                return False
        elif not _leaf_announces_every_turn(item):
            return False

    return True


def _as_one_condition(config: ConfigType | list[ConfigType]) -> ConfigType:
    """Turn a condition sequence into the single condition it means.

    The `condition` selector both surfaces advertise hands over a sequence,
    even for one condition and even when what was written was a single
    mapping: `cv.CONDITIONS_SCHEMA` normalises to a list. A sequence means all
    of them, as it does everywhere else in Home Assistant, so more than one
    becomes an `and`.
    """
    if not isinstance(config, list):
        return config

    if not config:
        msg = "A condition is required, and this one is empty."
        raise vol.Invalid(msg)

    if len(config) == 1:
        return config[0]

    return {CONF_CONDITION: "and", CONF_CONDITIONS: config}


def _run_scoped_names(config: ConfigType) -> set[str]:
    """Return the run-scoped names the templates in a condition reach for."""
    found: set[str] = set()

    for template in iter_templates(config):
        try:
            parsed = _JINJA.parse(template.template)
        except jinja2.TemplateSyntaxError:
            # Home Assistant has already accepted this template, so a bare
            # Jinja that chokes on it is this check falling short rather than
            # the config being wrong. Stay quiet instead of refusing.
            continue

        found |= RUN_SCOPED_NAMES.intersection(
            jinja_meta.find_undeclared_variables(parsed)
        )

    return found


class ConditionWatcher:
    """Watches a condition and reports when it turns true.

    Only the turn. A condition that is already true when watching starts is
    not a change, and callers that care about the current value ask for it.

    Reports the state change that made it turn, when it can be sure that is
    what made it turn, so whoever flipped the switch stays attributable. It
    can be sure only when every part of the condition announces its own turns;
    see `_announces_every_turn`. Otherwise, and for the backstop, it hands
    over nothing rather than something that might be the wrong thing.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        checker: ConditionChecker,
        entity_ids: set[str],
        on_met: Callable[[Event[EventStateChangedData] | None], None],
        *,
        announces_every_turn: bool,
    ) -> None:
        """Initialize the watcher."""
        self._hass = hass
        self._checker = checker
        self._entity_ids = entity_ids
        self._on_met = on_met
        self._announces_every_turn = announces_every_turn
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
            async_track_time_interval(
                self._hass,
                self._async_look_again,
                BACKSTOP,
                # Nothing should still be polling while Home Assistant is
                # shutting down, and a timer that outlives the run it belongs
                # to is a leak whether anyone notices or not.
                cancel_on_shutdown=True,
            )
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
    def _async_entity_changed(self, event: Event[EventStateChangedData]) -> None:
        """Ask again, because something the condition depends on moved.

        Carries that change along, the way Home Assistant's own template
        trigger does, so whoever is behind it can still be found. Only when
        this change really is what turned the condition, though.
        """
        self._async_look(event if self._announces_every_turn else None)

    @callback
    def _async_look_again(self, _now: datetime) -> None:
        """Ask again, because the backstop came round."""
        self._async_look(None)

    @callback
    def _async_look(self, event: Event[EventStateChangedData] | None) -> None:
        """Ask again, and report only a turn from false to true."""
        met = self._async_ask()
        if met == self._met:
            return

        self._met = met
        if met:
            self._on_met(event)


async def async_validate_condition(
    hass: HomeAssistant,
    config: ConfigType | list[ConfigType],
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
        hass, cv.CONDITION_SCHEMA(_as_one_condition(config))
    )

    if unwatchable := CONTEXT_DEPENDENT.intersection(_condition_types(validated)):
        msg = (
            "Cannot watch a condition that asks about the run it is in: "
            f"{', '.join(sorted(unwatchable))}. There is no run here, so the "
            "answer would not mean anything."
        )
        raise vol.Invalid(msg)

    if run_scoped := _run_scoped_names(validated):
        msg = (
            "Cannot watch a condition whose template reaches for "
            f"{', '.join(sorted(run_scoped))}, which only a running automation "
            "or script provides. There is no run here to take it from."
        )
        raise vol.Invalid(msg)

    return validated


async def async_condition_watcher(
    hass: HomeAssistant,
    validated: ConfigType,
    on_met: Callable[[Event[EventStateChangedData] | None], None],
) -> ConditionWatcher:
    """Build a watcher for an already validated condition, ready to start."""
    checker = await condition.async_from_config(hass, validated)
    return ConditionWatcher(
        hass,
        checker,
        condition.async_extract_entities(validated),
        on_met,
        announces_every_turn=_announces_every_turn(validated),
    )
