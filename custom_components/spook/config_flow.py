"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class UptimeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Spook."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle a flow initialized someone that didn't read the warnings."""
        if self._async_current_entries():
            return self.async_abort(reason="already_spooked")

        if user_input is not None:
            return self.async_create_entry(title="Not your homie", data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
