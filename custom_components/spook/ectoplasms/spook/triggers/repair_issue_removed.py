"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.trigger import Trigger

from ..repair_issues import DOMAIN_ONLY_FILTER_SCHEMA, as_filter

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): DOMAIN_ONLY_FILTER_SCHEMA,
    }
)


class SpookTrigger(Trigger):
    """Spook trigger that fires when a repair issue goes away.

    Something got fixed, or whatever was complaining stopped complaining.
    Useful for closing a notification you opened when the issue turned up.

    There is no severity to filter on here. By the time the registry
    announces a removal the entry is already gone, so the only things left to
    say about it are which integration it belonged to and what it was called.
    """

    trigger = "repair_issue_removed"

    _domains: set[str] | None

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,  # noqa: ARG003
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config."""
        return _TRIGGER_SCHEMA(config)  # type: ignore[no-any-return]

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        options: dict[str, Any] = config.options or {}
        self._domains, _ = as_filter(options)

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def issue_registry_changed(event: Event) -> None:
            """Look at what the registry just did."""
            if event.data["action"] != "remove":
                return

            domain = event.data["domain"]
            if self._domains is not None and domain not in self._domains:
                return

            issue_id = event.data["issue_id"]
            run_action(
                {"domain": domain, "issue_id": issue_id},
                f"repair issue {domain}/{issue_id} removed",
            )

        return self._hass.bus.async_listen(
            ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED, issue_registry_changed
        )
