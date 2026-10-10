"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.update import ATTR_INSTALLED_VERSION
from homeassistant.const import CONF_OPTIONS, CONF_TARGET, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, callback, split_entity_id
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import Trigger

from ....target_watching import watchable_target

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State
    from homeassistant.helpers.event import EventStateChangedData
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): watchable_target,
        vol.Optional(CONF_OPTIONS, default=dict): {},
    }
)


def _installed_version(state: State | None) -> str | None:
    """Return the version an update entity says is installed, if it says."""
    if state is None:
        return None
    version = state.attributes.get(ATTR_INSTALLED_VERSION)
    return None if version is None else str(version)


def _only_update_entities(entity_ids: set[str]) -> set[str]:
    """Keep the update entities, as an area or a label holds all sorts."""
    return {
        entity_id
        for entity_id in entity_ids
        if split_entity_id(entity_id)[0] == "update"
    }


# Everything here is called by the base class or by an event, so there is
# nothing public to count.
# pylint: disable-next=too-few-public-methods
class _VersionTracker(TargetEntityChangeTracker):
    """Watch a target's update entities and report a new installed version.

    The installed version is the only thing that says an update happened.
    `in_progress` does not: plenty of entities never set it, a device that
    updates itself skips it entirely, and one that does set it can drop it
    before the device is back to report its new version.

    The last version seen is remembered through unavailable, because
    firmware updates reboot the device. It goes away mid-install and comes
    back on the new version, and that return is the install.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        on_install: Callable[[str, Event[EventStateChangedData], str, str], None],
    ) -> None:
        """Initialize the tracker."""
        # Update entities are configuration entities unless an integration
        # says otherwise, and a device or area normally leaves those out. Here
        # that would leave out the very entities this trigger is for, so they
        # are taken in, the way core's own battery triggers take in theirs.
        super().__init__(
            hass,
            target_selection,
            entity_filter=_only_update_entities,
            primary_entities_only=False,
        )
        self._on_install = on_install
        self._tracked: set[str] = set()
        self._known_version: dict[str, str] = {}
        self._unsub_changes: list[CALLBACK_TYPE] = []
        self._unsub_started: CALLBACK_TYPE | None = None

        # Nothing is remembered until Home Assistant is up. Integrations fill
        # in their versions as they set up, some from a restored guess and
        # then from the device, and none of that is an install.
        # `is_running` is not the question: that is already true while Home
        # Assistant is starting, which is the half of a start this sits out.
        self._recording = hass.state is CoreState.running
        if not self._recording:
            self._unsub_started = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._house_is_up
            )

    @callback
    def _house_is_up(self, _event: Event) -> None:
        """Start remembering, from the versions everything is on now."""
        self._unsub_started = None
        self._recording = True
        self._remember_versions()

    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Re-aim at the entities the target now covers.

        The base class re-expands the target on every entity, device and area
        registry event anywhere in the system, and almost none of those move
        this target. Rebuilding the listeners each time would be work for
        nothing.
        """
        if tracked_entities == self._tracked:
            return

        for entity_id in self._tracked - tracked_entities:
            self._known_version.pop(entity_id, None)

        self._tracked = tracked_entities
        self._relisten()
        self._remember_versions()

    @callback
    def _remember_versions(self) -> None:
        """Note the version each newly watched entity is on.

        Only for the ones not known yet. Those are the starting point, not a
        change: an entity coming into the target is not an install.
        """
        if not self._recording:
            return

        for entity_id in self._tracked - self._known_version.keys():
            version = _installed_version(self._hass.states.get(entity_id))
            if version is not None:
                self._known_version[entity_id] = version

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

    @callback
    def _entity_changed(self, event: Event[EventStateChangedData]) -> None:
        """Compare the installed version against the last one seen."""
        entity_id: str = event.data["entity_id"]

        if event.data["new_state"] is None:
            # Removed. Whatever it comes back as is a new entity.
            self._known_version.pop(entity_id, None)
            return

        if not self._recording:
            return

        if (version := _installed_version(event.data["new_state"])) is None:
            # Unavailable, or not saying. The last version seen stands, so a
            # device rebooting into new firmware is compared with what it was
            # on before it went.
            return

        previous = self._known_version.get(entity_id)
        self._known_version[entity_id] = version

        # The first version seen is where it starts, not something it moved
        # to. An entity that reports its version late has not installed it.
        if previous is None or previous == version:
            return

        self._on_install(entity_id, event, previous, version)

    def _unsubscribe(self) -> None:
        """Unsubscribe from everything, the base class' listeners included."""
        super()._unsubscribe()

        if self._unsub_started is not None:
            self._unsub_started()
            self._unsub_started = None

        for unsub in self._unsub_changes:
            unsub()
        self._unsub_changes.clear()

        self._known_version.clear()
        self._tracked = set()


class SpookTrigger(Trigger):
    """Spook trigger that fires when an update entity's installed version changes.

    Home Assistant tells you when an update is available, but not when one
    went in. This fires when it did: whether somebody pressed install, the
    device updated itself, or it was installed outside of Home Assistant.
    A rollback is a change of version too, and fires the same way.
    """

    trigger = "update_installed"

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
        self._target = config.target or {}

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def version_installed(
            entity_id: str,
            event: Event[EventStateChangedData],
            from_version: str,
            to_version: str,
        ) -> None:
            """Run the action for the entity on its new version."""
            to_state = event.data["new_state"]
            payload: dict[str, Any] = {
                "entity_id": entity_id,
                "from_state": event.data["old_state"],
                "to_state": to_state,
                "from_version": from_version,
                "to_version": to_version,
            }

            run_action(
                payload,
                f"{entity_id} went from {from_version} to {to_version}",
                # Carried through, so Spook's own context conditions can tell
                # whether a person pressed install.
                to_state.context if to_state else None,
            )

        tracker = _VersionTracker(
            self._hass, TargetSelection(self._target), version_installed
        )
        return await tracker.async_setup()
