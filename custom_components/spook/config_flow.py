"""Spook - Your homie."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryDisabler,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.loader import async_get_integration

from .const import DOMAIN, NEWSLETTER_URL, REPOSITORY_URL, SPONSOR_URL


class UptimeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Spook."""

    VERSION = 1
    _disabled_entry: ConfigEntry | None = None

    def _async_get_user_disabled_entry(self) -> ConfigEntry | None:
        """Return an existing user-disabled Spook config entry."""
        for entry in self._async_current_entries():
            if entry.disabled_by is ConfigEntryDisabler.USER:
                return entry
        return None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by someone that didn't read the warnings."""
        if current_entries := self._async_current_entries():
            if any(entry.disabled_by is None for entry in current_entries):
                return self.async_abort(reason="already_spooked")

            self._disabled_entry = self._async_get_user_disabled_entry()
            if self._disabled_entry is not None:
                return self.async_show_menu(
                    step_id="already_configured",
                    menu_options=["enable_existing", "keep_sleeping"],
                )

            return self.async_abort(reason="already_spooked")

        integration = await async_get_integration(self.hass, DOMAIN)
        if user_input is not None:
            return self.async_create_entry(
                title="Your homie",
                data={},
                description="spooked",
                description_placeholders={
                    "documentation_url": str(integration.documentation),
                    "newsletter_url": NEWSLETTER_URL,
                    "repository_url": REPOSITORY_URL,
                    "sponsor_url": SPONSOR_URL,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={
                "issue_tracker_url": str(integration.issue_tracker),
            },
        )

    async def async_step_already_configured(
        self,
        _: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle an already configured disabled Spook entry."""
        self._disabled_entry = self._async_get_user_disabled_entry()
        if self._disabled_entry is None:
            return self.async_abort(reason="already_spooked")

        return self.async_show_menu(
            step_id="already_configured",
            menu_options=["enable_existing", "keep_sleeping"],
        )

    async def async_step_enable_existing(
        self,
        _: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Enable the existing disabled Spook config entry."""
        self._disabled_entry = self._async_get_user_disabled_entry()
        if self._disabled_entry is None:
            return self.async_abort(reason="already_spooked")

        if await self.hass.config_entries.async_set_disabled_by(
            self._disabled_entry.entry_id,
            disabled_by=None,
        ):
            return self.async_abort(reason="enabled_existing")

        return self.async_abort(reason="enable_failed")

    async def async_step_keep_sleeping(
        self,
        _: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Leave the existing disabled Spook config entry alone."""
        return self.async_abort(reason="kept_sleeping")
