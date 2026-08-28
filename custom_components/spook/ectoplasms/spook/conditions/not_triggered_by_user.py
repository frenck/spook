"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.helpers.condition import Condition

from ..context import run_context

if TYPE_CHECKING:
    from typing import Unpack

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import ConditionCheckParams
    from homeassistant.helpers.typing import ConfigType

# Takes nothing. An empty options block is accepted and normalised, the same
# shape Home Assistant gives an option-less condition, but anything actually
# set is rejected rather than quietly dropped.
_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default=dict): vol.Schema({}),
    }
)


class SpookCondition(Condition):
    """Spook condition that passes when nobody set this run going.

    The counterpart of ``spook.triggered_by_user``, and a separate condition
    on purpose: picking "not triggered by a user" from the list says what it
    does, where a negated option on the other one would have to be read
    twice.

    It takes no options. "Not started by anyone" is a different question
    from "not started by this particular person", and answering both from
    one condition is how you end up with a condition nobody can read.

    It passes for anything Spook cannot attribute to a person, which
    includes a run forced through ``automation.trigger``.
    """

    condition = "not_triggered_by_user"
    # Asks about the run it is in, so it cannot be watched or checked
    # outside one. `condition_watching` refuses these.
    needs_run_context = True

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,  # noqa: ARG003
        config: ConfigType,
    ) -> ConfigType:
        """Validate the condition config."""
        return _CONDITION_SCHEMA(config)  # type: ignore[no-any-return]

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Return True when no user started this run."""
        context = run_context(kwargs.get("variables"))
        return context is None or context.user_id is None
