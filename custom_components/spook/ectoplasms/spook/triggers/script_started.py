"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.script.const import (
    ATTR_LAST_TRIGGERED,
    DOMAIN as SCRIPT_DOMAIN,
)
from homeassistant.const import CONF_OPTIONS, CONF_TARGET, EVENT_STATE_CHANGED
from homeassistant.core import callback, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import Trigger

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.event import EventStateChangedData
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

# `TARGET_FIELDS` is a plain mapping of schema fields, so it needs compiling
# before it can validate anything.
_TARGET_SCHEMA = vol.Schema(cv.TARGET_FIELDS)


def _target_or_everything(value: Any) -> ConfigType | None:
    """Validate the target, where one that names nothing means everything.

    The editor hands over an empty target when nothing is picked, so that has
    to mean the same as leaving it out: every script.
    """
    target: ConfigType = _TARGET_SCHEMA(value or {})
    return target if TargetSelection(target).has_any_target else None


_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TARGET): _target_or_everything,
        vol.Optional(CONF_OPTIONS, default=dict): {},
    }
)


@callback
def _is_a_script_starting(event_data: EventStateChangedData) -> bool:
    """Tell whether a state change is a script starting a run.

    Home Assistant stamps `last_triggered` once a run has been let through,
    and writes the state right after. A run refused because the script is
    already running, or has as many runs as it may, never gets that far.

    A script that comes in fresh, at a start or a reload, has no state before
    it, and its stamp is the one it had already.
    """
    if split_entity_id(event_data["entity_id"])[0] != SCRIPT_DOMAIN:
        return False

    old_state = event_data["old_state"]
    new_state = event_data["new_state"]
    if old_state is None or new_state is None:
        return False

    started = new_state.attributes.get(ATTR_LAST_TRIGGERED)
    return started is not None and started != old_state.attributes.get(
        ATTR_LAST_TRIGGERED
    )


# Everything here is called by the base class, so there is nothing public to
# count.
# pylint: disable-next=too-few-public-methods
class _ScriptTracker(TargetEntityChangeTracker):
    """Keep the set of scripts a target covers up to date.

    The registry listening and target re-expansion come from the base class,
    which calls back into `_handle_entities_update` whenever the set moves.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        on_update: Callable[[set[str]], None],
    ) -> None:
        """Initialize the tracker."""
        # No filter of its own: whatever else an area or label holds never
        # gets past the event filter, which only lets scripts through.
        super().__init__(hass, target_selection, entity_filter=lambda ids: ids)
        self._on_update = on_update

    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Hand over the scripts the target now covers."""
        self._on_update(tracked_entities)


class SpookTrigger(Trigger):
    """Spook trigger that fires when a script starts a run.

    Home Assistant fires an event for it, but finding that event, and typing
    its name and the script into an event trigger, is not something the
    editor helps with. It also fires for runs that are refused straight
    after, like a second one for a script that may only run once at a time.

    This one has a target picker, and only fires for a run that starts.
    """

    trigger = "script_started"

    _target: ConfigType | None

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
        self._target = config.target

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        # Only consulted with a target. Without one, every script counts.
        watched: set[str] = set()

        @callback
        def _watch(scripts: set[str]) -> None:
            """Take over the scripts the target covers now."""
            watched.clear()
            watched.update(scripts)

        @callback
        def _started(event: Event[EventStateChangedData]) -> None:
            """Run the action for the script that started."""
            entity_id = event.data["entity_id"]
            if self._target is not None and entity_id not in watched:
                return

            to_state = event.data["new_state"]
            payload: dict[str, Any] = {
                "entity_id": entity_id,
                "from_state": event.data["old_state"],
                "to_state": to_state,
            }
            run_action(
                payload,
                f"{entity_id} started",
                # Carried through, so Spook's own context conditions can tell
                # who started it.
                to_state.context if to_state else None,
            )

        unsubs: list[CALLBACK_TYPE] = [
            self._hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                _started,
                event_filter=_is_a_script_starting,
            )
        ]
        if self._target is not None:
            tracker = _ScriptTracker(self._hass, TargetSelection(self._target), _watch)
            unsubs.append(await tracker.async_setup())

        @callback
        def _detach() -> None:
            """Stop watching."""
            for unsub in unsubs:
                unsub()

        return _detach
