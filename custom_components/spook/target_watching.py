"""Spook - Your homie. Shared rules for triggers that watch a target.

Every trigger that watches a target's entities needs the same thing from the
configuration before it can start: a target that actually names something. The
rule lived in two of them and had already begun to drift apart in its wording,
so it lives here now.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.event import EventStateChangedData
    from homeassistant.helpers.typing import ConfigType

# `TARGET_FIELDS` is a plain mapping of schema fields, so it needs compiling
# before it can validate anything.
_TARGET_SCHEMA = vol.Schema(cv.TARGET_FIELDS)


def watchable_target(value: Any) -> ConfigType:
    """Validate the target, and refuse one that names nothing.

    An empty target passes the field validation happily and then watches
    nothing at all: a trigger that loads and can never fire. Core's own target
    tracking helper raises on this for the same reason.
    """
    target: ConfigType = _TARGET_SCHEMA(value)
    if not TargetSelection(target).has_any_target:
        message = (
            "The target must name at least one entity, device, area, floor or label"
        )
        raise vol.Invalid(message)
    return target


# Everything here is called by the base class or by an event, so there is
# nothing public to count.
# pylint: disable-next=too-few-public-methods
class StateChangeWatcher(TargetEntityChangeTracker):
    """Watch the state changes of exactly the entities a target covers.

    The part triggers on a target share: keeping one listener on the right
    entities while the target moves underneath it. What a change means is up
    to the trigger, in `_entity_changed`.

    The registry listening and target re-expansion come from the base class,
    which calls back into `_handle_entities_update` whenever the set of
    targeted entities moves.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        entity_filter: Callable[[set[str]], set[str]],
    ) -> None:
        """Initialize the watcher."""
        super().__init__(hass, target_selection, entity_filter=entity_filter)
        self._tracked: set[str] = set()
        self._unsub_changes: list[CALLBACK_TYPE] = []

    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Re-aim at the entities the target now covers.

        The base class re-expands the target on every entity, device and area
        registry event anywhere in the system, and almost none of those move
        this target.
        """
        if tracked_entities == self._tracked:
            return

        self._tracked = tracked_entities
        self._relisten()

    @callback
    def _relisten(self) -> None:
        """Listen for changes to exactly the entities being tracked.

        The new listener goes on before the old one comes off. Home Assistant
        keeps one shared tracker per event type: drop the last subscriber and
        it is torn down, taking with it events that have fired but not been
        dispatched yet.
        """
        previous = self._unsub_changes
        self._unsub_changes = []

        if self._tracked:
            self._unsub_changes = [
                async_track_state_change_event(
                    self._hass, list(self._tracked), self._entity_changed
                )
            ]

        for unsub in previous:
            unsub()

    @abstractmethod
    @callback
    def _entity_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle a state change of one of the entities being tracked."""

    def _unsubscribe(self) -> None:
        """Unsubscribe from everything, the base class' listeners included."""
        super()._unsubscribe()

        for unsub in self._unsub_changes:
            unsub()
        self._unsub_changes.clear()
        self._tracked = set()
