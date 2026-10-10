"""Spook - Your homie."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import Condition
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from typing import Unpack

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import ConditionCheckParams, ConditionConfig
    from homeassistant.helpers.typing import ConfigType

CONF_DURATION = "duration"

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_DURATION): cv.positive_time_period,
        },
    }
)


def _last_triggered(variables: Any) -> datetime | None:
    """Return when the current automation or script last ran, if known."""
    this = (variables or {}).get("this")
    if not isinstance(this, dict):
        return None

    # Home Assistant parses the restored value back into a datetime before it
    # reaches the state machine, so this is never the raw ISO string.
    raw = this.get("attributes", {}).get("last_triggered")
    return raw if isinstance(raw, datetime) else None


class SpookCondition(Condition):
    """Spook condition that passes only after a per-run cooldown.

    Passes when this automation or script has not run within the given
    duration (or has never run), so it does not re-fire too often. Replaces
    the copy-pasted ``now() - this.attributes.last_triggered`` template.
    """

    condition = "cooldown"
    # Asks about the run it is in, so it cannot be watched or checked
    # outside one. `condition_watching` refuses these.
    needs_run_context = True

    _duration: timedelta

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
        self._duration = options[CONF_DURATION]

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Return True when the cooldown has elapsed since the last run."""
        last_triggered = _last_triggered(kwargs.get("variables"))
        if last_triggered is None:
            # Never ran (or no context); the cooldown is satisfied.
            return True
        return dt_util.utcnow() - last_triggered >= self._duration
