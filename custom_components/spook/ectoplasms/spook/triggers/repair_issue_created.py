"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.trigger import Trigger

from ..repair_issues import FILTER_SCHEMA, as_filter, matches, payload

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
        vol.Required(CONF_OPTIONS, default=dict): FILTER_SCHEMA,
    }
)


class SpookTrigger(Trigger):
    """Spook trigger that fires when a repair issue turns up.

    Home Assistant collects these on the repairs page and waits to be
    visited. This is for the ones you would rather hear about: an integration
    reporting it needs attention, or Spook finding a reference to something
    that no longer exists.

    Only genuinely new issues fire it. Re-reporting an issue that is already
    there is an update as far as the registry is concerned, which is what
    keeps a repair that is checked on a schedule from firing every time.
    """

    trigger = "repair_issue_created"

    _domains: set[str] | None
    _severities: set[str] | None

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
        self._domains, self._severities = as_filter(options)

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        registry = ir.async_get(self._hass)

        @callback
        def issue_registry_changed(event: Event) -> None:
            """Look at what the registry just did."""
            if event.data["action"] != "create":
                return

            issue = registry.async_get_issue(
                event.data["domain"], event.data["issue_id"]
            )
            if issue is None or not matches(issue, self._domains, self._severities):
                return

            run_action(
                payload(issue),
                f"repair issue {issue.domain}/{issue.issue_id} created",
            )

        return self._hass.bus.async_listen(
            ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED, issue_registry_changed
        )
