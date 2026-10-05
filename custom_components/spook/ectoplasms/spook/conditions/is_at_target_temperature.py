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
from homeassistant.helpers.condition import Condition
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)

from ....target_watching import watchable_target
from ....temperature_targets import (
    CONF_TOLERANCE,
    only_climate_and_water_heaters,
    reading,
    validate_tolerance,
)

if TYPE_CHECKING:
    from typing import Unpack

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import ConditionCheckParams, ConditionConfig
    from homeassistant.helpers.typing import ConfigType

CONF_BEHAVIOR = "behavior"
BEHAVIOR_ANY = "any"
BEHAVIOR_ALL = "all"

# Not the device saying anything about itself, so not a no either. Left out
# of the question, the same as Home Assistant's own entity conditions do.
_NOT_ANSWERING = (STATE_UNAVAILABLE, STATE_UNKNOWN)

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): watchable_target,
        vol.Optional(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
                [BEHAVIOR_ANY, BEHAVIOR_ALL]
            ),
            vol.Optional(CONF_TOLERANCE, default=0.0): validate_tolerance,
        },
    }
)


class SpookCondition(Condition):
    """Spook condition that passes when a temperature is at its target.

    The question the trigger for reaching the target answers once, asked
    whenever you like: is the bathroom warm yet, is the water hot. Read the
    same way the trigger reads it, so the two never disagree.
    """

    condition = "is_at_target_temperature"
    # Reads only the devices' states, so it can be asked outside of a run,
    # and watched.
    needs_run_context = False

    _target: ConfigType
    _all: bool
    _tolerance: float

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
        self._tolerance = options.get(CONF_TOLERANCE, 0.0)

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:  # noqa: ARG002
        """Return whether the targeted devices are at their target."""
        selected = async_extract_referenced_entity_ids(
            self._hass, TargetSelection(self._target), expand_group=False
        )
        entity_ids = only_climate_and_water_heaters(
            selected.referenced | selected.indirectly_referenced
        )
        answers = [
            (current := reading(state)) is not None
            and current.at_target(self._tolerance)
            for entity_id in entity_ids
            if (state := self._hass.states.get(entity_id)) is not None
            and state.state not in _NOT_ANSWERING
        ]

        # Nothing left to ask is not a yes, whatever "all" makes of an empty
        # list: a bathroom whose thermostat is unavailable is not known to be
        # warm.
        if not answers:
            return False
        return all(answers) if self._all else any(answers)
