"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_DELAY,
    CONF_FOR,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback, split_entity_id
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.helpers.trigger import Trigger

from ....target_watching import StateChangeWatcher

if TYPE_CHECKING:
    from collections.abc import Callable, Container, Iterable
    from datetime import datetime, timedelta

    from homeassistant.core import (
        CALLBACK_TYPE,
        Context,
        Event,
        HomeAssistant,
        State,
    )
    from homeassistant.helpers.event import EventStateChangedData
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

CONF_ATTRIBUTE_CHANGES = "attribute_changes"
CONF_BEHAVIOR = "behavior"
CONF_BLIP_TOLERANCE = "blip_tolerance"
CONF_CONFIG_ENTRY = "config_entry"
CONF_DEVICE_CLASS = "device_class"
CONF_DOMAIN = "domain"
CONF_EXCLUDE_CONFIG_ENTRY = "exclude_config_entry"
CONF_EXCLUDE_DEVICE_CLASS = "exclude_device_class"
CONF_EXCLUDE_DOMAIN = "exclude_domain"
CONF_EXCLUDE_INTEGRATION = "exclude_integration"
CONF_EXCLUDE_TARGET = "exclude_target"
CONF_FROM = "from"
CONF_IGNORE_UNAVAILABLE = "ignore_unavailable"
CONF_INTEGRATION = "integration"
CONF_NOT_FROM = "not_from"
CONF_NOT_TO = "not_to"
CONF_TO = "to"

BEHAVIOR_ALL = "all"
BEHAVIOR_EACH = "each"
BEHAVIOR_FIRST = "first"

# States that are not the entity saying anything about itself.
_NOT_A_VALUE = frozenset({STATE_UNAVAILABLE, STATE_UNKNOWN})

# `TARGET_FIELDS` is a plain mapping of schema fields, so it needs compiling
# before it can validate anything. An exclude target may be empty: leaving
# nothing out is a fine thing to ask for.
_EXCLUDE_TARGET_SCHEMA = vol.Schema(cv.TARGET_FIELDS)

# Values are compared as text, because that is what the editor hands over. A
# brightness of 255 and a "255" typed into a field are the same thing.
_VALUES = vol.All(cv.ensure_list, [cv.string])


def _no_contradictions(options: dict[str, Any]) -> dict[str, Any]:
    """Refuse options that ask for two things that cannot both be true."""
    for wanted, unwanted in ((CONF_FROM, CONF_NOT_FROM), (CONF_TO, CONF_NOT_TO)):
        if wanted in options and unwanted in options:
            message = f"Use either {wanted} or {unwanted}, not both"
            raise vol.Invalid(message)

    # Listing unavailable while ignoring it would be a trigger that loads and
    # then quietly never fires for exactly the case it names.
    if options[CONF_IGNORE_UNAVAILABLE]:
        for key in (CONF_FROM, CONF_TO):
            if named := _NOT_A_VALUE.intersection(options.get(key, [])):
                message = (
                    f"{key} names {', '.join(sorted(named))}, which is ignored; "
                    f"turn off {CONF_IGNORE_UNAVAILABLE} to trigger on it"
                )
                raise vol.Invalid(message)

    # The editor leaves an emptied target behind as `{}`. Naming nothing to
    # leave out is the same as not asking, so the exclude lists then apply to
    # everything the target covers, whichever way it was written.
    if (
        CONF_EXCLUDE_TARGET in options
        and not TargetSelection(options[CONF_EXCLUDE_TARGET]).has_any_target
    ):
        options = {
            key: value for key, value in options.items() if key != CONF_EXCLUDE_TARGET
        }

    # First and all are about getting somewhere. Without a state to get to,
    # every state is already there, and the trigger could never fire.
    if options[CONF_BEHAVIOR] != BEHAVIOR_EACH and not (
        CONF_TO in options or CONF_NOT_TO in options
    ):
        message = (
            f"{CONF_BEHAVIOR} {options[CONF_BEHAVIOR]} needs {CONF_TO} or "
            f"{CONF_NOT_TO}: a state for the target to get to"
        )
        raise vol.Invalid(message)

    if CONF_BLIP_TOLERANCE in options and CONF_FOR not in options:
        message = f"{CONF_BLIP_TOLERANCE} only means something together with {CONF_FOR}"
        raise vol.Invalid(message)

    return options


_OPTIONS_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_DOMAIN): _VALUES,
            vol.Optional(CONF_INTEGRATION): _VALUES,
            vol.Optional(CONF_CONFIG_ENTRY): _VALUES,
            vol.Optional(CONF_DEVICE_CLASS): _VALUES,
            vol.Optional(CONF_EXCLUDE_TARGET): _EXCLUDE_TARGET_SCHEMA,
            vol.Optional(CONF_EXCLUDE_DOMAIN): _VALUES,
            vol.Optional(CONF_EXCLUDE_INTEGRATION): _VALUES,
            vol.Optional(CONF_EXCLUDE_CONFIG_ENTRY): _VALUES,
            vol.Optional(CONF_EXCLUDE_DEVICE_CLASS): _VALUES,
            vol.Optional(CONF_ATTRIBUTE): cv.string,
            vol.Optional(CONF_FROM): _VALUES,
            vol.Optional(CONF_NOT_FROM): _VALUES,
            vol.Optional(CONF_TO): _VALUES,
            vol.Optional(CONF_NOT_TO): _VALUES,
            vol.Optional(CONF_IGNORE_UNAVAILABLE, default=True): cv.boolean,
            # Following an attribute, every change is an attribute change, so
            # this has nothing to add there.
            vol.Optional(CONF_ATTRIBUTE_CHANGES, default=False): cv.boolean,
            vol.Optional(CONF_BEHAVIOR, default=BEHAVIOR_EACH): vol.In(
                [BEHAVIOR_EACH, BEHAVIOR_FIRST, BEHAVIOR_ALL]
            ),
            vol.Optional(CONF_FOR): cv.positive_time_period,
            vol.Optional(CONF_BLIP_TOLERANCE): cv.positive_time_period,
            vol.Optional(CONF_DELAY): cv.positive_time_period,
        }
    ),
    _no_contradictions,
)

# `TARGET_FIELDS` is a plain mapping of schema fields, so it needs compiling
# before it can validate anything.
_TARGET_SCHEMA = vol.Schema(cv.TARGET_FIELDS)

_SELECTORS = (CONF_DOMAIN, CONF_INTEGRATION, CONF_CONFIG_ENTRY, CONF_DEVICE_CLASS)


def _target_or_nothing(value: Any) -> ConfigType | None:
    """Validate the target, where one that names nothing is no target.

    The editor hands over an empty target when nothing is picked, so that
    has to mean the same as leaving it out.
    """
    target: ConfigType = _TARGET_SCHEMA(value)
    return target if TargetSelection(target).has_any_target else None


def _selects_something(config: ConfigType) -> ConfigType:
    """Refuse a trigger without a target that does not pick anything either.

    Without a target, the domain, integration, entry and device class lists
    pick the entities from everything Home Assistant has. Without those as
    well, it would be every entity in the house, which is a mistake rather
    than a setting.
    """
    if config.get(CONF_TARGET) is None and not any(
        config[CONF_OPTIONS].get(key) for key in _SELECTORS
    ):
        message = (
            "Give a target, or pick entities by domain, integration, "
            "integration entry or device class"
        )
        raise vol.Invalid(message)
    return config


_TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_TARGET): _target_or_nothing,
            vol.Optional(CONF_OPTIONS, default=dict): _OPTIONS_SCHEMA,
        }
    ),
    _selects_something,
)


@dataclass(frozen=True, kw_only=True)
class _EntityFilter:
    """Which entities a list of domains, integrations and so on keeps.

    Within one list any match will do, across lists all of them must hold:
    a door sensor from Zigbee is a binary sensor, from ZHA, of class door.
    """

    domains: frozenset[str] = frozenset()
    integrations: frozenset[str] = frozenset()
    config_entries: frozenset[str] = frozenset()
    device_classes: frozenset[str] = frozenset()

    @classmethod
    def from_options(cls, options: dict[str, Any], prefix: str = "") -> _EntityFilter:
        """Build the filter from the options, with or without `exclude_`."""
        return cls(
            domains=frozenset(options.get(f"{prefix}{CONF_DOMAIN}", [])),
            integrations=frozenset(options.get(f"{prefix}{CONF_INTEGRATION}", [])),
            config_entries=frozenset(options.get(f"{prefix}{CONF_CONFIG_ENTRY}", [])),
            device_classes=frozenset(options.get(f"{prefix}{CONF_DEVICE_CLASS}", [])),
        )

    @property
    def is_empty(self) -> bool:
        """Return whether this filter asks for nothing at all."""
        return not (
            self.domains
            or self.integrations
            or self.config_entries
            or self.device_classes
        )

    @callback
    def keep(self, hass: HomeAssistant, entity_ids: Iterable[str]) -> set[str]:
        """Return the entities that pass every list that was given."""
        if self.is_empty:
            return set(entity_ids)

        registry = er.async_get(hass)
        return {
            entity_id
            for entity_id in entity_ids
            if self._passes(entity_id, registry.async_get(entity_id))
        }

    def _passes(self, entity_id: str, entry: er.RegistryEntry | None) -> bool:
        """Return whether one entity passes every list that was given.

        Integration, entry and device class come from the entity registry,
        because a change there is what makes the target look again. An entity
        without a registry entry has none of them, so it never passes those.
        Reading the device class from its state instead would be a filter that
        only looks once, and keeps a door that has since become a window.
        """
        if self.domains and split_entity_id(entity_id)[0] not in self.domains:
            return False

        if self.integrations and (
            entry is None or entry.platform not in self.integrations
        ):
            return False

        if self.config_entries and (
            entry is None or entry.config_entry_id not in self.config_entries
        ):
            return False

        return not self.device_classes or (
            entry is not None
            and (entry.device_class or entry.original_device_class)
            in self.device_classes
        )


@dataclass(frozen=True, kw_only=True)
class _Rules:
    """What counts as a change worth firing for, read from the options."""

    attribute: str | None
    from_values: frozenset[str] | None
    not_from_values: frozenset[str]
    to_values: frozenset[str] | None
    not_to_values: frozenset[str]
    ignore_unavailable: bool
    attribute_changes: bool

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> _Rules:
        """Build the rules from validated options."""

        def optional(key: str) -> frozenset[str] | None:
            return frozenset(options[key]) if key in options else None

        return cls(
            attribute=options.get(CONF_ATTRIBUTE),
            from_values=optional(CONF_FROM),
            not_from_values=frozenset(options.get(CONF_NOT_FROM, [])),
            to_values=optional(CONF_TO),
            not_to_values=frozenset(options.get(CONF_NOT_TO, [])),
            ignore_unavailable=options[CONF_IGNORE_UNAVAILABLE],
            attribute_changes=options[CONF_ATTRIBUTE_CHANGES],
        )

    def value(self, state: State) -> str | None:
        """Return what is being followed: the state, or one attribute of it."""
        if self.attribute is None:
            return state.state
        if (value := state.attributes.get(self.attribute)) is None:
            return None
        return str(value)

    def counts(self, state: State | None) -> bool:
        """Return whether a state takes part at all.

        Unavailable and unknown are the device saying nothing, and are left
        out unless asked for.
        """
        if state is None:
            return False
        return not (self.ignore_unavailable and state.state in _NOT_A_VALUE)

    def arrived(self, state: State) -> bool:
        """Return whether a state is one the trigger is waiting for."""
        value = self.value(state)
        if self.to_values is not None and value not in self.to_values:
            return False
        return value not in self.not_to_values

    def left(self, state: State) -> bool:
        """Return whether a state is one the trigger may come from."""
        value = self.value(state)
        if self.from_values is not None and value not in self.from_values:
            return False
        return value not in self.not_from_values

    def changed(self, old: State, new: State) -> bool:
        """Return whether anything changed that is being followed."""
        if self.attribute is not None:
            return self.value(old) != self.value(new)
        if old.state != new.state:
            return True
        return self.attribute_changes and old.attributes != new.attributes


@dataclass(kw_only=True)
class _Waiting:
    """A change that qualified and now has to hold for the duration."""

    fire: Callable[[], None]
    # What has to hold, for each: the value it changed to. Another value that
    # also passes `to` is still a change, so it calls the wait off.
    value: str | None = None
    # The entities that went quiet while holding, and are inside the
    # tolerance. They count as still holding until they are back.
    away: set[str] = field(default_factory=set)
    cancel_timer: CALLBACK_TYPE | None = None
    cancel_blip: CALLBACK_TYPE | None = None
    # The duration ran out while the entity was away. It fires the moment
    # the entity comes back as it was, inside the tolerance.
    due: bool = False

    def cancel(self) -> None:
        """Stop every timer this is holding."""
        if self.cancel_timer is not None:
            self.cancel_timer()
            self.cancel_timer = None
        if self.cancel_blip is not None:
            self.cancel_blip()
            self.cancel_blip = None


@dataclass(frozen=True, kw_only=True)
class _Timing:
    """How long a change has to hold, may be away, and waits before firing."""

    duration: timedelta | None
    blip_tolerance: timedelta | None
    delay: timedelta | None


@dataclass(frozen=True, kw_only=True)
class _Settings:
    """Everything the watcher needs to know, read once from the options."""

    rules: _Rules
    include: _EntityFilter
    exclude: _EntityFilter
    exclude_target: ConfigType | None
    behavior: str
    timing: _Timing


# Everything here is called by the base class or by an event, so there is
# nothing public to count.
# pylint: disable-next=too-few-public-methods
class _StateWatcher(StateChangeWatcher):
    """Watch what a target covers, and decide what is worth firing for.

    Without a target, the include lists pick from everything instead.

    How `for` and behavior combine follows Home Assistant's own entity
    triggers: each entity on its own, the first one of the target, or the
    moment all of them are there. A duration is kept per entity for each,
    and for the target as a whole for first and all.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        settings: _Settings,
        on_change: Callable[[str, State, State, Context], None],
    ) -> None:
        """Initialize the watcher."""
        self._settings = settings
        self._on_change = on_change
        self._states: dict[str, State | None] = {}
        self._waiting: dict[str, _Waiting] = {}
        self._picking = not target_selection.has_any_target
        super().__init__(hass, target_selection, entity_filter=self._wanted)

    @callback
    def _wanted(self, entity_ids: set[str]) -> set[str]:
        """Return what is left of the target after both filters.

        Leaving out is done without the primary entities rule: excluding an
        area should exclude everything in it, the diagnostic entities too.
        Leaving out too much does no harm here, too little does.
        """
        settings = self._settings
        if self._picking:
            entity_ids = self._everything()
        included = settings.include.keep(self._hass, entity_ids)

        if settings.exclude_target:
            selected = async_extract_referenced_entity_ids(
                self._hass,
                TargetSelection(settings.exclude_target),
                expand_group=False,
                primary_entities_only=False,
            )
            candidates = selected.referenced | selected.indirectly_referenced
        elif not settings.exclude.is_empty:
            candidates = included
        else:
            return included

        return included - settings.exclude.keep(self._hass, candidates)

    @callback
    def _everything(self) -> set[str]:
        """Return everything the include lists can pick from.

        The primary entities in the registry, as a target through a device
        or area would give, and the entities without a registry entry, which
        only a domain can pick. Those are found when the registry changes,
        not the moment their first state is written.
        """
        registry = er.async_get(self._hass)
        primary = {
            entity_id
            for entity_id, entry in registry.entities.items()
            if entry.entity_category is None
        }
        unregistered = {
            entity_id
            for entity_id in self._hass.states.async_entity_ids()
            if entity_id not in registry.entities
        }
        return primary | unregistered

    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Follow the target as it moves, and drop what no longer belongs."""
        if tracked_entities == self._tracked:
            return

        for entity_id in self._tracked - tracked_entities:
            self._states.pop(entity_id, None)
            if (waiting := self._waiting.pop(entity_id, None)) is not None:
                waiting.cancel()
        for entity_id in tracked_entities - self._tracked:
            self._states[entity_id] = self._hass.states.get(entity_id)

        super()._handle_entities_update(tracked_entities)

        # A new entity that is not there yet breaks an all, and one leaving
        # can take the only match of a first with it.
        group_key = self._settings.behavior
        if (waiting := self._waiting.get(group_key)) is not None:
            self._settle(group_key, waiting)

    def _count(self, away: Container[str] = ()) -> tuple[int, int]:
        """Return how many entities are there, out of how many take part.

        Those away inside the tolerance count as still there.
        """
        rules = self._settings.rules
        matches = included = 0
        for entity_id, state in self._states.items():
            if entity_id in away:
                included += 1
                matches += 1
                continue
            if state is None or not rules.counts(state):
                continue
            included += 1
            if rules.arrived(state):
                matches += 1
        return matches, included

    def _together_still_there(self, away: Container[str] = ()) -> bool:
        """Return whether first or all still holds for the target."""
        matches, included = self._count(away)
        if self._settings.behavior == BEHAVIOR_FIRST:
            return matches >= 1
        # Nothing taking part at all is not everything being there.
        if not included:
            return False
        return matches == included

    @callback
    def _entity_changed(self, event: Event[EventStateChangedData]) -> None:
        """Decide what one change means."""
        entity_id: str = event.data["entity_id"]
        old: State | None = event.data["old_state"]
        new: State | None = event.data["new_state"]

        # Kept as of this event rather than read live: events arrive one
        # loop turn after the state machine moved on, and the live states
        # may already hold later changes of other entities.
        self._states[entity_id] = new

        if self._waiting and self._recheck_waiting(entity_id, old, new):
            # Coming back from a blip is the old state carrying on, not a
            # new change to start counting from.
            return

        if old is not None and new is not None and self._qualifies(old, new):
            self._qualified(entity_id, old, new, event.context)

    def _qualifies(self, old: State, new: State) -> bool:
        """Return whether a change is one to fire for, durations aside."""
        rules = self._settings.rules
        if not (rules.counts(old) and rules.counts(new) and rules.changed(old, new)):
            return False
        if not (rules.left(old) and rules.arrived(new)):
            return False

        behavior = self._settings.behavior
        if behavior == BEHAVIOR_EACH:
            return True

        # Already there before is not getting there: the count of entities
        # that are there did not move.
        if rules.arrived(old):
            return False

        # Those away inside a tolerance still count as there: a second door
        # opening while the first is in a blip is not the first door open.
        away = waiting.away if (waiting := self._waiting.get(behavior)) else ()
        matches, included = self._count(away)
        if behavior == BEHAVIOR_FIRST:
            return matches == 1
        return matches == included

    @callback
    def _recheck_waiting(
        self, entity_id: str, old: State | None, new: State | None
    ) -> bool:
        """Keep, pause or drop what is waiting out a duration.

        Returns whether the wait took this change for its own: going away
        inside the tolerance, or coming back from it as it was. Neither is a
        new change to start counting from, even where unavailable counts.
        """
        behavior = self._settings.behavior
        key = entity_id if behavior == BEHAVIOR_EACH else behavior
        if (waiting := self._waiting.get(key)) is None:
            return False

        if new is not None and new.state in _NOT_A_VALUE:
            # Flickering between unavailable and unknown while away lands
            # here too. For each it is simply away again; for first and all
            # it was not holding a moment ago, and the target, still counting
            # it as there, carries on below.
            if self._settings.timing.blip_tolerance and self._was_holding(old):
                waiting.away.add(entity_id)
                self._start_blip(key, waiting)
                return True
        elif entity_id in waiting.away:
            waiting.away.discard(entity_id)
            if self._holds(waiting, new):
                self._settle(key, waiting)
                return True

        if self._still_holds(waiting, new):
            self._settle(key, waiting)
        else:
            self._waiting.pop(key)
            waiting.cancel()
        return False

    def _was_holding(self, old: State | None) -> bool:
        """Return whether an entity that just went quiet was holding.

        For each, the entity has a wait of its own, so it was. For first and
        all, only one that was there takes a blip with it; one that was not
        going away changes nothing about the target.
        """
        if self._settings.behavior == BEHAVIOR_EACH:
            return True
        rules = self._settings.rules
        return old is not None and rules.counts(old) and rules.arrived(old)

    def _holds(self, waiting: _Waiting, new: State | None) -> bool:
        """Return whether an entity is as the wait needs it to be."""
        rules = self._settings.rules
        if new is None or not rules.counts(new):
            return False
        if self._settings.behavior == BEHAVIOR_EACH:
            return rules.value(new) == waiting.value
        return rules.arrived(new)

    def _still_holds(self, waiting: _Waiting, new: State | None) -> bool:
        """Return whether what is waiting can carry on after this change."""
        if self._settings.behavior == BEHAVIOR_EACH:
            return self._holds(waiting, new)
        return self._together_still_there(waiting.away)

    @callback
    def _settle(self, key: str, waiting: _Waiting) -> None:
        """Drop a wait that no longer holds, or end a blip that is over.

        A blip is over once nobody is away anymore. If the duration ran out
        during it, that is the moment to fire.
        """
        if self._settings.behavior != BEHAVIOR_EACH and not (
            self._together_still_there(waiting.away)
        ):
            self._waiting.pop(key)
            waiting.cancel()
            return

        if waiting.away or waiting.cancel_blip is None:
            return

        waiting.cancel_blip()
        waiting.cancel_blip = None

        if waiting.due:
            self._waiting.pop(key)
            waiting.fire()

    @callback
    def _start_blip(self, key: str, waiting: _Waiting) -> None:
        """Give what went quiet the tolerance to come back in.

        The tolerance counts from the first moment something went quiet, not
        from the last flicker inside the blip.
        """
        if waiting.cancel_blip is not None or not (
            tolerance := self._settings.timing.blip_tolerance
        ):
            return

        @callback
        def blip_too_long(_now: datetime) -> None:
            """Stop counting the ones still away as there.

            For each, that ends the wait: the entity is not back. For first
            and all, the target is judged again as it really is.
            """
            waiting.cancel_blip = None
            waiting.away.clear()
            if self._waiting.get(key) is not waiting:
                return

            if self._settings.behavior == BEHAVIOR_EACH or not (
                self._together_still_there()
            ):
                self._waiting.pop(key)
                waiting.cancel()
                return

            if waiting.due:
                self._waiting.pop(key)
                waiting.fire()

        waiting.cancel_blip = async_call_later(self._hass, tolerance, blip_too_long)

    def _holds_without_the_away(self) -> bool:
        """Return whether first or all holds even counting the away as away.

        Then there is nothing to wait for: the target is there regardless of
        whether the ones that went quiet come back.
        """
        if self._settings.behavior == BEHAVIOR_EACH:
            return False
        return self._together_still_there()

    @callback
    def _qualified(
        self, entity_id: str, old: State, new: State, context: Context
    ) -> None:
        """Fire now, or once the change has held for the duration."""
        settings = self._settings

        @callback
        def fire() -> None:
            self._on_change(entity_id, old, new, context)

        if not (duration := settings.timing.duration):
            fire()
            return

        key = entity_id if settings.behavior == BEHAVIOR_EACH else settings.behavior
        if (previous := self._waiting.pop(key, None)) is not None:
            previous.cancel()

        waiting = _Waiting(fire=fire, value=settings.rules.value(new))

        @callback
        def held_long_enough(_now: datetime) -> None:
            """Fire, unless what has to hold is away right now."""
            waiting.cancel_timer = None
            if waiting.away and not self._holds_without_the_away():
                # Whether it held is decided when they come back, or do not.
                waiting.due = True
                return
            self._waiting.pop(key)
            if waiting.cancel_blip is not None:
                waiting.cancel_blip()
                waiting.cancel_blip = None
            fire()

        waiting.cancel_timer = async_call_later(self._hass, duration, held_long_enough)
        self._waiting[key] = waiting

    def _unsubscribe(self) -> None:
        """Stop watching, and drop everything that was still waiting."""
        super()._unsubscribe()

        for waiting in self._waiting.values():
            waiting.cancel()
        self._waiting.clear()
        self._states.clear()


class SpookTrigger(Trigger):
    """Spook's state trigger.

    Home Assistant's state trigger takes entities. This one takes a target,
    so a label or an area works, filtered down by domain, integration,
    config entry or device class, and with things left out again. On top
    of that: unavailable and unknown ignored unless you ask for them,
    attribute changes ignored, a duration that survives a blip, and a
    delay.
    """

    trigger = "state_changed"

    _options: dict[str, Any]
    _target: ConfigType

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
        self._options = dict(config.options or {})
        self._target = config.target or {}

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        options = self._options
        settings = _Settings(
            rules=_Rules.from_options(options),
            include=_EntityFilter.from_options(options),
            exclude=_EntityFilter.from_options(options, prefix="exclude_"),
            exclude_target=options.get(CONF_EXCLUDE_TARGET),
            behavior=options[CONF_BEHAVIOR],
            timing=_Timing(
                duration=options.get(CONF_FOR),
                blip_tolerance=options.get(CONF_BLIP_TOLERANCE),
                delay=options.get(CONF_DELAY),
            ),
        )
        timing = settings.timing
        pending_delays: set[CALLBACK_TYPE] = set()

        @callback
        def run(entity_id: str, old: State, new: State, context: Context) -> None:
            """Run the action for the entity that changed."""
            run_action(
                {
                    "entity_id": entity_id,
                    "from_state": old,
                    "to_state": new,
                    "for": timing.duration,
                    "delay": timing.delay,
                },
                f"state of {entity_id}",
                # Carried through, so Spook's own context conditions can still
                # tell who was behind the change.
                context,
            )

        @callback
        def changed(entity_id: str, old: State, new: State, context: Context) -> None:
            """Run now, or after the delay, whatever happens in between."""
            if not timing.delay:
                run(entity_id, old, new, context)
                return

            @callback
            def delayed(_now: datetime) -> None:
                pending_delays.discard(cancel)
                run(entity_id, old, new, context)

            cancel = async_call_later(self._hass, timing.delay, delayed)
            pending_delays.add(cancel)

        watcher = _StateWatcher(
            self._hass, TargetSelection(self._target), settings, changed
        )
        unsubscribe = await watcher.async_setup()

        @callback
        def detach() -> None:
            """Stop watching, and drop delays that have not run yet."""
            unsubscribe()
            for cancel in pending_delays:
                cancel()
            pending_delays.clear()

        return detach
