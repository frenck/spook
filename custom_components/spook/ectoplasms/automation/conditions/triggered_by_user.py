"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import Condition

from ..context import run_context

if TYPE_CHECKING:
    from typing import Unpack

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import ConditionCheckParams, ConditionConfig
    from homeassistant.helpers.typing import ConfigType

CONF_USER_ID = "user_id"

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_USER_ID): vol.All(cv.ensure_list, [cv.string]),
        },
    }
)


def _user_ids(configured: Any) -> set[str] | None:
    """Return the configured user IDs as a set, or None for "anyone".

    Config validation turns a single ID into a list, but a condition can be
    instantiated from a config that never went through it. A bare string
    handed to ``set()`` becomes a set of letters, which matches nothing and
    explains nothing, so coerce here rather than trust the caller.
    """
    if not configured:
        return None
    if isinstance(configured, str):
        return {configured}
    return {str(user_id) for user_id in configured}


class SpookCondition(Condition):
    """Spook condition that passes when a person set this run going.

    A run started from the interface, the app, or an API call carries the
    user it was made by. A run started by a schedule, a state change, or
    another automation does not. This condition tells those apart, and can
    narrow to specific users.
    """

    # Registered under the automation domain rather than Spook's own: the
    # leading underscore tells Home Assistant to take the key as absolute.
    condition = "_automation.triggered_by_user"

    _user_ids: set[str] | None

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
        self._user_ids = _user_ids(options.get(CONF_USER_ID))

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Return True when a user started this run."""
        context = run_context(kwargs.get("variables"))
        if context is None or context.user_id is None:
            return False

        if self._user_ids is None:
            return True

        return context.user_id in self._user_ids
