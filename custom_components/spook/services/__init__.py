"""Spook - Not your homey."""
import random

from homeassistant.backports.enum import StrEnum
from homeassistant.components import homeassistant
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import _load_services_file, async_set_service_schema
from homeassistant.loader import async_get_integration

from ..const import DOMAIN


class SpookServices(StrEnum):
    """Spook services."""

    DISABLE_CONFIG_ENTRY = "disable_config_entry"
    DISABLE_DEVICE = "disable_device"
    ENABLE_CONFIG_ENTRY = "enable_config_entry"
    ENABLE_DEVICE = "enable_device"
    RANDOM_FAIL = "random_fail"


@callback
async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Spook services."""
    # Ensure cache is populated
    integration = await async_get_integration(hass, DOMAIN)
    services_file = await hass.async_add_executor_job(
        _load_services_file, hass, integration
    )

    async def _async_random_fail(_: ServiceCall) -> None:
        """Randomly let this service call fail."""
        if random.choice([True, False]):
            raise HomeAssistantError("Spooked!")

    hass.services.async_register(
        DOMAIN,
        SpookServices.RANDOM_FAIL,
        _async_random_fail,
    )

    async def _async_disable_config_entry(call: ServiceCall) -> None:
        """Service to disable a config entry."""
        await hass.config_entries.async_set_disabled_by(
            call.data["config_entry_id"], ConfigEntryDisabler.USER
        )

    hass.services.async_register(
        homeassistant.DOMAIN,
        SpookServices.DISABLE_CONFIG_ENTRY,
        _async_disable_config_entry,
    )

    async_set_service_schema(
        hass,
        homeassistant.DOMAIN,
        SpookServices.DISABLE_CONFIG_ENTRY,
        services_file[SpookServices.DISABLE_CONFIG_ENTRY],
    )

    async def _async_enable_config_entry(call: ServiceCall) -> None:
        """Service to disable a config entry."""
        await hass.config_entries.async_set_disabled_by(
            call.data["config_entry_id"], None
        )

    hass.services.async_register(
        homeassistant.DOMAIN,
        SpookServices.ENABLE_CONFIG_ENTRY,
        _async_enable_config_entry,
    )

    async_set_service_schema(
        hass,
        homeassistant.DOMAIN,
        SpookServices.ENABLE_CONFIG_ENTRY,
        services_file[SpookServices.ENABLE_CONFIG_ENTRY],
    )

    async def _async_disable_device(call: ServiceCall) -> None:
        """Service to disable a device."""
        device_registry = dr.async_get(hass)
        device_registry.async_update_device(
            device_id=call.data["device_id"],
            disabled_by=dr.DeviceEntryDisabler.USER,
        )

    hass.services.async_register(
        homeassistant.DOMAIN,
        SpookServices.DISABLE_DEVICE,
        _async_disable_device,
    )

    async_set_service_schema(
        hass,
        homeassistant.DOMAIN,
        SpookServices.DISABLE_DEVICE,
        services_file[SpookServices.DISABLE_DEVICE],
    )

    async def _async_enable_device(call: ServiceCall) -> None:
        """Service to enable a device."""
        device_registry = dr.async_get(hass)
        device_registry.async_update_device(
            device_id=call.data["device_id"],
            disabled_by=None,
        )

    hass.services.async_register(
        homeassistant.DOMAIN,
        SpookServices.ENABLE_DEVICE,
        _async_enable_device,
    )

    async_set_service_schema(
        hass,
        homeassistant.DOMAIN,
        SpookServices.ENABLE_DEVICE,
        services_file[SpookServices.ENABLE_DEVICE],
    )
