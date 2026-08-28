"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import Condition

from ....run_history import MAX_RUNS_REMEMBERED, async_get_run_history
from ..context import own_entity_id

if TYPE_CHECKING:
    from typing import Unpack

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import ConditionCheckParams, ConditionConfig
    from homeassistant.helpers.typing import ConfigType

    from ....run_history import RunHistory

CONF_LIMIT = "limit"
CONF_PERIOD = "period"


def _limit(value: Any) -> int:
    """Validate the limit, and refuse anything that is not a whole count.

    `vol.Coerce(int)` hands back 1 for both 1.5 and `True`, so a mistyped
    limit would quietly become a different one. And only half quietly: 0.5 is
    already refused, because truncating it lands below the minimum. An
    allowance is a number of runs, so it has to be a whole one.
    """
    message = f"The limit must be a whole number of runs, got '{value}'"

    # A bool is an int as far as Python is concerned, and `True` would sail
    # through everything below as a limit of one.
    if isinstance(value, bool):
        raise vol.Invalid(message)

    try:
        as_number = float(value)
    except (TypeError, ValueError) as err:
        raise vol.Invalid(message) from err

    if not as_number.is_integer():
        raise vol.Invalid(message)

    return int(vol.Range(min=1, max=MAX_RUNS_REMEMBERED)(int(as_number)))


def _period(value: Any) -> timedelta:
    """Validate the period, and refuse one nothing can fit inside."""
    period = cv.positive_time_period(value)
    if period <= timedelta(0):
        message = "The period must be longer than zero"
        raise vol.Invalid(message)
    return period


_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_LIMIT): _limit,
            vol.Required(CONF_PERIOD): _period,
        },
    }
)


class SpookCondition(Condition):
    """Spook condition that passes until a run allowance is used up.

    Passes while this automation has run fewer than the given number of times
    within the given period, so something can be held to a few runs an hour or
    a handful a day. The counterpart to ``spook.cooldown``, which spaces runs
    out rather than capping them.

    The window rolls: a limit of five over a day means no more than five runs
    in any twenty-four hours, not five between midnights. Runs are counted
    from what actually ran, so a run some other condition turned down does
    not cost anything.

    Automations only. See ``run_history`` for why scripts are left out.
    """

    condition = "quota"

    _limit: int
    _period: timedelta

    # Core refuses to check a condition it has not set up, so by the time any
    # check runs this is always there.
    _history: RunHistory

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
        self._limit = options[CONF_LIMIT]
        self._period = options[CONF_PERIOD]

    async def _async_setup(self) -> None:
        """Take hold of the history of what ran when."""
        self._history = async_get_run_history(self._hass)

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Return True while there is allowance left."""
        variables = kwargs.get("variables")
        entity_id = own_entity_id(variables)
        if entity_id is None:
            # Nothing to count against, so nothing has been used up.
            return True

        # The run this is part of does not count against the allowance. A
        # script announces itself before its sequence starts, so without this
        # a limit of one would turn down the very first run.
        context = variables.get("context") if hasattr(variables, "get") else None

        used = self._history.async_runs_within(
            entity_id, self._period, ignoring=getattr(context, "id", None)
        )
        return used < self._limit
