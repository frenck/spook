"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.const import CONF_OPTIONS
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import Condition

from ....automation_runs import async_get_automation_runs
from ..context import own_entity_id, source_contexts

if TYPE_CHECKING:
    from typing import Unpack

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import ConditionCheckParams, ConditionConfig
    from homeassistant.helpers.typing import ConfigType

    from ....automation_runs import AutomationRuns

CONF_AUTOMATION = "automation"


_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_AUTOMATION): cv.entities_domain(AUTOMATION_DOMAIN),
        },
    }
)


class SpookCondition(Condition):
    """Spook condition that passes when another automation set this run going.

    Home Assistant gives an automation run its own context, and everything
    that run writes carries it. So an automation reacting to a change another
    automation made finds that context on its trigger, and it survives a
    script in between.

    What it cannot do is turn a context back into the automation that owns
    it: nothing in Home Assistant keeps that. So Spook listens for automations
    announcing themselves and remembers the mapping for the last few hundred
    runs, which is plenty, since the run being asked about happened a moment
    ago.

    The automation doing the asking does not count as an answer. Put this
    inside an action sequence and its own run is the nearest context in
    reach, so without skipping it the condition would pass for a schedule or
    a person just as readily.

    Can be narrowed to specific automations.
    """

    condition = "triggered_by_automation"

    _automation_entity_ids: set[str] | None

    # Core refuses to check a condition it has not set up, so by the time any
    # check runs this is always there.
    _runs: AutomationRuns

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
        automation = options.get(CONF_AUTOMATION)
        if isinstance(automation, str):
            # Config validation turns a single entity ID into a list, and a
            # condition can be built from a config that never went through it.
            automation = [automation]
        self._automation_entity_ids = set(automation) if automation else None

    async def _async_setup(self) -> None:
        """Take hold of the register that knows which automation ran when."""
        self._runs = async_get_automation_runs(self._hass)

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Return True when another automation started this run."""
        variables = kwargs.get("variables")
        myself = own_entity_id(variables)

        for context in source_contexts(variables):
            entity_id = self._runs.async_which(context.id)

            # Keep looking rather than settling for the first answer. The
            # nearest context inside an action sequence is this run's own, and
            # a context that resolves to an automation nobody asked about says
            # nothing about the ones further out.
            if entity_id is None or entity_id == myself:
                continue

            if (
                self._automation_entity_ids is None
                or entity_id in self._automation_entity_ids
            ):
                return True

        return False
