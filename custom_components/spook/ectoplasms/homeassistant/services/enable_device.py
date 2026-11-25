"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from ....const import DOMAIN as SPOOK_DOMAIN
from ....services import AbstractSpookAdminService
from ..device import async_enable_device_and_parent

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to enable a device."""

    domain = DOMAIN
    service = "enable_device"
    schema = {vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string])}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        device_registry = dr.async_get(self.hass)

        # Checked before anything is written, so a refused call changes
        # nothing.
        for device_id in call.data["device_id"]:
            self._raise_if_disabled_by_its_integration_entry(device_registry, device_id)

        for device_id in call.data["device_id"]:
            async_enable_device_and_parent(device_registry, device_id)

    def _raise_if_disabled_by_its_integration_entry(
        self,
        device_registry: dr.DeviceRegistry,
        device_id: str,
    ) -> None:
        """Refuse a device that is off because its integration entry is.

        Home Assistant ignores enabling such a device: it comes back with its
        integration entry, not on its own. Without this the action would do
        nothing and say nothing. #2082.
        """
        device = device_registry.async_get(device_id)
        if (
            device is None
            or device.disabled_by is not dr.DeviceEntryDisabler.CONFIG_ENTRY
        ):
            return

        entry = self.hass.config_entries.async_get_entry(
            getattr(device, "config_entry_id", None) or device.primary_config_entry
        )

        raise HomeAssistantError(
            translation_domain=SPOOK_DOMAIN,
            translation_key="device_disabled_by_integration_entry",
            translation_placeholders={
                "device_id": device_id,
                "entry": entry.title if entry is not None else "unknown",
            },
        )
