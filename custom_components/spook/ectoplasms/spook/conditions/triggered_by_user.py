"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.person import (
    ATTR_USER_ID,
    DOMAIN as PERSON_DOMAIN,
)
from homeassistant.const import CONF_OPTIONS
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import Condition

from ..context import run_context

if TYPE_CHECKING:
    from typing import Unpack

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.condition import ConditionCheckParams, ConditionConfig
    from homeassistant.helpers.typing import ConfigType

CONF_PERSON = "person"

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_PERSON): cv.entities_domain(PERSON_DOMAIN),
        },
    }
)


class SpookCondition(Condition):
    """Spook condition that passes when a person set this run going.

    What it can see is the user behind the trigger. A state change or an
    event somebody caused carries the account that caused it, so an
    automation reacting to that finds them. A schedule, a template, or an
    integration acting on its own carries nobody, and neither does a run
    forced through ``automation.trigger``: Home Assistant hands the caller's
    context to the automation but the run itself starts a fresh one, and
    nothing resolves it back.

    Can be narrowed to specific people.
    """

    condition = "triggered_by_user"

    _person_entity_ids: list[str] | None

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
        person = options.get(CONF_PERSON)
        if isinstance(person, str):
            # Config validation turns a single entity ID into a list, and a
            # condition can be built from a config that never went through it.
            person = [person]
        self._person_entity_ids = list(person) if person else None

    def _user_ids(self) -> set[str]:
        """Return the user accounts the configured people are linked to.

        Read per check rather than cached: which account a person is linked
        to is a setting somebody can change without reloading anything, and
        a person may have no account at all, in which case they contribute
        nothing and this condition cannot pass for them.
        """
        user_ids = set()
        for entity_id in self._person_entity_ids or ():
            if (state := self._hass.states.get(entity_id)) is None:
                continue
            if user_id := state.attributes.get(ATTR_USER_ID):
                user_ids.add(user_id)
        return user_ids

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Return True when a user started this run."""
        context = run_context(kwargs.get("variables"))
        if context is None or context.user_id is None:
            return False

        if self._person_entity_ids is None:
            return True

        return context.user_id in self._user_ids()
