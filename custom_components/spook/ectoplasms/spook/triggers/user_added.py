"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.auth import EVENT_USER_ADDED
from homeassistant.const import CONF_OPTIONS
from homeassistant.helpers.trigger import Trigger

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

_TRIGGER_SCHEMA = vol.Schema({vol.Optional(CONF_OPTIONS, default=dict): {}})


class SpookTrigger(Trigger):
    """Spook trigger that fires when somebody is given a login.

    Home Assistant fires an event for it and nothing else: no notification, no
    log line worth the name. A new person able to log in to your house is
    something an admin would rather hear about than stumble upon.

    Users Home Assistant makes for itself are left out. An integration that
    needs to act on its own, Supervisor or the cloud for one, is handed a user
    of its own when it is set up, and nobody can log in as one of those.
    """

    trigger = "user_added"

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,  # noqa: ARG003
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config."""
        return _TRIGGER_SCHEMA(config)  # type: ignore[no-any-return]

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        async def user_added(event: Event) -> None:
            """Fire for the new user, if it is one somebody can log in as.

            The event carries only the ID, so the rest is looked up. A user
            removed again before that is no longer anybody's news.
            """
            user = await self._hass.auth.async_get_user(event.data["user_id"])
            if user is None or user.system_generated:
                return

            run_action(
                {
                    "user_id": user.id,
                    "name": user.name,
                    "is_admin": user.is_admin,
                },
                f"user {user.name} added",
                event.context,
            )

        return self._hass.bus.async_listen(EVENT_USER_ADDED, user_added)
