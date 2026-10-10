"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.helpers.condition import Condition

from ..repair_issues import FILTER_SCHEMA, active_issues, as_filter, matches

if TYPE_CHECKING:
    from typing import Unpack

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import ConditionCheckParams, ConditionConfig
    from homeassistant.helpers.typing import ConfigType

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): FILTER_SCHEMA,
    }
)


class SpookCondition(Condition):
    """Spook condition that passes while a repair issue is outstanding.

    For holding something back until the house is in order: not running a
    nightly job while an integration is complaining, or nagging once a day
    for as long as anything is wrong.

    Issues somebody has ignored do not count. Ignoring one is telling Home
    Assistant to stop bringing it up, and this is not the place to overrule
    that.
    """

    condition = "repair_issue_present"
    needs_run_context = False

    _domains: set[str] | None
    _severities: set[str] | None

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
        self._domains, self._severities = as_filter(options)

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:  # noqa: ARG002
        """Return True while anything asked about is outstanding."""
        return any(
            matches(issue, self._domains, self._severities)
            for issue in active_issues(self._hass)
        )
