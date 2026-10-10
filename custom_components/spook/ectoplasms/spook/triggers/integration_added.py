"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    SOURCE_IGNORE,
    ConfigEntryChange,
)
from homeassistant.const import CONF_OPTIONS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import Trigger

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

_TRIGGER_SCHEMA = vol.Schema({vol.Optional(CONF_OPTIONS, default=dict): {}})


class SpookTrigger(Trigger):
    """Spook trigger that fires when an integration is added.

    Read off the same signal `integration_failed` follows, which Home
    Assistant sends for every change a configuration entry goes through.
    Entries loaded at start-up are not added, they were already there, so a
    restart does not report the whole house over again.
    """

    trigger = "integration_added"

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

        @callback
        def entry_changed(change: ConfigEntryChange, entry: ConfigEntry) -> None:
            """Fire for an entry that was just added.

            Ignoring a discovered device is stored as an entry too, one that
            exists so the discovery is not offered again. Nothing was set up,
            so it is not an integration being added.
            """
            if change is not ConfigEntryChange.ADDED or entry.source == SOURCE_IGNORE:
                return

            run_action(
                {
                    "entry_id": entry.entry_id,
                    "domain": entry.domain,
                    "title": entry.title,
                    "source": entry.source,
                },
                f"{entry.title} ({entry.domain}) added",
            )

        return async_dispatcher_connect(
            self._hass, SIGNAL_CONFIG_ENTRY_CHANGED, entry_changed
        )
