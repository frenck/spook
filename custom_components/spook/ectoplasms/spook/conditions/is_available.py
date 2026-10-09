"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import (
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.condition import Condition
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)

from ....target_watching import watchable_target

if TYPE_CHECKING:
    from typing import Unpack

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import ConditionCheckParams, ConditionConfig
    from homeassistant.helpers.typing import ConfigType

CONF_BEHAVIOR = "behavior"
BEHAVIOR_ANY = "any"
BEHAVIOR_ALL = "all"

# Not there to talk to: gone from its integration, or not saying anything yet.
_NOT_THERE = (STATE_UNAVAILABLE, STATE_UNKNOWN)

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): watchable_target,
        vol.Optional(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
                [BEHAVIOR_ANY, BEHAVIOR_ALL]
            ),
        },
    }
)


class SpookCondition(Condition):
    """Spook condition that passes when an entity is there to talk to.

    A speaker that is not always powered, a smart plug that comes and goes.
    Written by hand it is a `not` around a state condition listing
    `unavailable` and `unknown`, every time. #1831.
    """

    condition = "is_available"
    # Reads only the states, so it can be asked outside of a run, and watched.
    needs_run_context = False

    _target: ConfigType
    _all: bool

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,  # noqa: ARG003
        config: ConfigType,
    ) -> ConfigType:
        """Validate the condition config."""
        return _CONDITION_SCHEMA(config)  # type: ignore[no-any-return]

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize the condition."""
        super().__init__(hass, config)
        options: dict[str, Any] = config.options or {}
        self._target = config.target or {}
        self._all = options.get(CONF_BEHAVIOR, BEHAVIOR_ANY) == BEHAVIOR_ALL

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:  # noqa: ARG002
        """Return whether the targeted entities are available."""
        selected = async_extract_referenced_entity_ids(
            self._hass, TargetSelection(self._target), expand_group=False
        )

        # An entity named outright and missing altogether is about as
        # unavailable as it gets. One that only comes along with a device or
        # an area is left out when it is disabled: that is not a reason for a
        # whole room to count as unavailable. Enabled and without a state, its
        # integration is not there, and neither is it.
        entity_registry = er.async_get(self._hass)
        answers = [self._is_there(entity_id) for entity_id in selected.referenced]
        answers.extend(
            self._is_there(entity_id)
            for entity_id in selected.indirectly_referenced - selected.referenced
            if (entry := entity_registry.async_get(entity_id)) is None
            or entry.disabled_by is None
        )

        # Nothing to ask is not a yes, whatever `all` makes of an empty list.
        if not answers:
            return False
        return all(answers) if self._all else any(answers)

    def _is_there(self, entity_id: str) -> bool:
        """Return whether an entity has a state that is not unavailable."""
        state = self._hass.states.get(entity_id)
        return state is not None and state.state not in _NOT_THERE
