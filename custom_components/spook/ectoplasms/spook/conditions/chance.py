"""Spook - Your homie."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.helpers.condition import Condition

if TYPE_CHECKING:
    from typing import Unpack

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import ConditionCheckParams, ConditionConfig
    from homeassistant.helpers.typing import ConfigType

CONF_PERCENTAGE = "percentage"

_HUNDRED_PERCENT = 100

# A chance condition does not need cryptographic randomness, but using the
# system RNG keeps the security scanners quiet without a suppression.
_RANDOM = random.SystemRandom()

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_PERCENTAGE): vol.All(
                vol.Coerce(float),
                vol.Range(min=0, max=_HUNDRED_PERCENT),
            ),
        },
    }
)


class SpookCondition(Condition):
    """Spook condition that passes a set percentage of the time, at random."""

    condition = "chance"

    _percentage: float

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
        self._percentage = options[CONF_PERCENTAGE]

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:  # noqa: ARG002
        """Return True for the configured percentage of checks."""
        return _RANDOM.random() * _HUNDRED_PERCENT < self._percentage
