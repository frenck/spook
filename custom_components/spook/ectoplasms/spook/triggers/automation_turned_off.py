"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.const import (
    CONF_OPTIONS,
    CONF_TARGET,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
)
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

    Every automation in the house is the question an admin asks most, and
    labelling each one just to be able to ask it would be a chore. The editor
    hands over an empty target when nothing is picked, so that has to mean
    the same as leaving it out.
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
def _is_an_automation_turning_off(event_data: EventStateChangedData) -> bool:
    """Tell whether a state change is an automation going from on to off.

    Only turning one off writes that. A reload, a new entity ID, or disabling
    it in the entity registry all take the automation away instead, without
    an off, and one that starts out off was never on.
    """
    if split_entity_id(event_data["entity_id"])[0] != AUTOMATION_DOMAIN:
        return False

    old_state = event_data["old_state"]
    new_state = event_data["new_state"]
    return (
        old_state is not None
        and new_state is not None
        and old_state.state == STATE_ON
        and new_state.state == STATE_OFF
    )


# Everything here is called by the base class, so there is nothing public to
# count.
# pylint: disable-next=too-few-public-methods
class _AutomationTracker(TargetEntityChangeTracker):
    """Keep the set of automations a target covers up to date.

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
        # gets past the event filter, which only lets automations through.
        super().__init__(hass, target_selection, entity_filter=lambda ids: ids)
        self._on_update = on_update

    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Hand over the automations the target now covers."""
        self._on_update(tracked_entities)


class SpookTrigger(Trigger):
    """Spook trigger that fires when an automation is turned off.

    An automation that is off does nothing, and says nothing about it either.
    Somebody turning one off while looking for a problem, and forgetting to
    turn it back on, is how a house quietly stops doing things.

    Whoever turned it off is on the context, so Spook's own context conditions
    can tell a person from an automation doing it.
    """

    trigger = "automation_turned_off"

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
        # Only consulted with a target. Without one, every automation counts.
        watched: set[str] = set()

        @callback
        def _watch(automations: set[str]) -> None:
            """Take over the automations the target covers now."""
            watched.clear()
            watched.update(automations)

        @callback
        def _turned_off(event: Event[EventStateChangedData]) -> None:
            """Run the action for the automation that was turned off."""
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
                f"{entity_id} was turned off",
                # Carried through, so Spook's own context conditions can tell
                # whether a person turned it off.
                to_state.context if to_state else None,
            )

        unsubs: list[CALLBACK_TYPE] = [
            self._hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                _turned_off,
                event_filter=_is_an_automation_turning_off,
            )
        ]
        if self._target is not None:
            tracker = _AutomationTracker(
                self._hass, TargetSelection(self._target), _watch
            )
            unsubs.append(await tracker.async_setup())

        @callback
        def _detach() -> None:
            """Stop watching."""
            for unsub in unsubs:
                unsub()

        return _detach
