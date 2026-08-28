"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
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

# Fewer than one run is not an allowance, it is a way of switching something off.
MIN_LIMIT = 1


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

    # Decimal rather than float, and from the text rather than the value.
    # `float("5.0000000000000001")` is exactly 5.0, so a fractional limit would
    # round its way through, and a large enough integer raises OverflowError on
    # the way in rather than being refused for being too large.
    try:
        as_decimal = Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError) as err:
        raise vol.Invalid(message) from err

    # Infinity and not-a-number are both "integral" as far as Decimal is
    # concerned, and only fall over on the way to an int.
    if not as_decimal.is_finite() or as_decimal != as_decimal.to_integral_value():
        raise vol.Invalid(message)

    # Range checked while it is still a Decimal, before anything becomes an
    # int. "1e1000000000" is twelve characters of config and a billion digits
    # of integer, and building it just to find out it is too large is the
    # whole cost: `int(Decimal("1e1000000"))` already takes 25 seconds, while
    # comparing the Decimal takes microseconds whatever the exponent.
    if not MIN_LIMIT <= as_decimal <= MAX_RUNS_REMEMBERED:
        message = (
            f"The limit must be between {MIN_LIMIT} and {MAX_RUNS_REMEMBERED} runs"
        )
        raise vol.Invalid(message)

    return int(as_decimal)


# The longest window on offer. The history lives in memory and is cleared by a
# restart, so an allowance measured over more than a year could not be answered
# honestly anyway, and a period long enough to reach past the start of the
# calendar crashes the subtraction it is used for.
MAX_PERIOD = timedelta(days=366)


def _period(value: Any) -> timedelta:
    """Validate the period, and refuse one nothing useful fits inside."""
    period = cv.positive_time_period(value)

    if period <= timedelta(0):
        message = "The period must be longer than zero"
        raise vol.Invalid(message)

    if period > MAX_PERIOD:
        message = f"The period must be {MAX_PERIOD.days} days or shorter"
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

        # The run this is part of does not count against the allowance. An
        # automation is recorded before its actions start, so a condition
        # sitting in an `if` finds its own run already there, and without this
        # a limit of one would turn down every run.
        context = variables.get("context") if hasattr(variables, "get") else None

        used = self._history.async_runs_within(
            entity_id, self._period, ignoring=getattr(context, "id", None)
        )
        return used < self._limit
