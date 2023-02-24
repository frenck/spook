"""Spook - Not your homey."""
import random

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
from homeassistant.components import homeassistant
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import _load_services_file, async_set_service_schema
from homeassistant.loader import async_get_integration

from ..const import DOMAIN


class SpookServices(StrEnum):
    """Spook services."""

    DISABLE_CONFIG_ENTRY = "disable_config_entry"
    DISABLE_DEVICE = "disable_device"
    DISABLE_ENTITY = "disable_entity"
    ENABLE_CONFIG_ENTRY = "enable_config_entry"
    ENABLE_DEVICE = "enable_device"
    ENABLE_ENTITY = "enable_entity"
    HIDE_ENTITY = "hide_entity"
    RANDOM_FAIL = "random_fail"
    UNHIDE_ENTITY = "unhide_entity"


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
        domain=DOMAIN,
        service=SpookServices.RANDOM_FAIL,
        service_func=_async_random_fail,
    )

    async def _async_disable_config_entry(call: ServiceCall) -> None:
        """Service to disable a config entry."""
        await hass.config_entries.async_set_disabled_by(
            call.data["config_entry_id"], ConfigEntryDisabler.USER
        )

    hass.services.async_register(
        domain=homeassistant.DOMAIN,
        service=SpookServices.DISABLE_CONFIG_ENTRY,
        service_func=_async_disable_config_entry,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): cv.string,
            }
        ),
    )

    async_set_service_schema(
        hass,
        domain=homeassistant.DOMAIN,
        service=SpookServices.DISABLE_CONFIG_ENTRY,
        schema=services_file[SpookServices.DISABLE_CONFIG_ENTRY],
    )

    async def _async_enable_config_entry(call: ServiceCall) -> None:
        """Service to disable a config entry."""
        await hass.config_entries.async_set_disabled_by(
            call.data["config_entry_id"], None
        )

    hass.services.async_register(
        domain=homeassistant.DOMAIN,
        service=SpookServices.ENABLE_CONFIG_ENTRY,
        service_func=_async_enable_config_entry,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): cv.string,
            }
        ),
    )

    async_set_service_schema(
        hass,
        domain=homeassistant.DOMAIN,
        service=SpookServices.ENABLE_CONFIG_ENTRY,
        schema=services_file[SpookServices.ENABLE_CONFIG_ENTRY],
    )

    async def _async_disable_device(call: ServiceCall) -> None:
        """Service to disable a device."""
        device_registry = dr.async_get(hass)
        device_registry.async_update_device(
            device_id=call.data["device_id"],
            disabled_by=dr.DeviceEntryDisabler.USER,
        )

    hass.services.async_register(
        domain=homeassistant.DOMAIN,
        service=SpookServices.DISABLE_DEVICE,
        service_func=_async_disable_device,
        schema=vol.Schema(
            {
                vol.Required("device_id"): cv.string,
            }
        ),
    )

    async_set_service_schema(
        hass,
        domain=homeassistant.DOMAIN,
        service=SpookServices.DISABLE_DEVICE,
        schema=services_file[SpookServices.DISABLE_DEVICE],
    )

    async def _async_enable_device(call: ServiceCall) -> None:
        """Service to enable a device."""
        device_registry = dr.async_get(hass)
        device_registry.async_update_device(
            device_id=call.data["device_id"],
            disabled_by=None,
        )

    hass.services.async_register(
        domain=homeassistant.DOMAIN,
        service=SpookServices.ENABLE_DEVICE,
        service_func=_async_enable_device,
        schema=vol.Schema(
            {
                vol.Required("device_id"): cv.string,
            }
        ),
    )

    async_set_service_schema(
        hass,
        domain=homeassistant.DOMAIN,
        service=SpookServices.ENABLE_DEVICE,
        schema=services_file[SpookServices.ENABLE_DEVICE],
    )

    async def _async_disable_entity(call: ServiceCall) -> None:
        """Service to disable an entity."""
        entity_registry = er.async_get(hass)
        for entity_id in call.data["entity_id"]:
            entity_registry.async_update_entity(
                entity_id=entity_id,
                disabled_by=er.RegistryEntryDisabler.USER,
            )

    hass.services.async_register(
        domain=homeassistant.DOMAIN,
        service=SpookServices.DISABLE_ENTITY,
        service_func=_async_disable_entity,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
    )

    async_set_service_schema(
        hass,
        domain=homeassistant.DOMAIN,
        service=SpookServices.DISABLE_ENTITY,
        schema=services_file[SpookServices.DISABLE_ENTITY],
    )

    async def _async_enable_entity(call: ServiceCall) -> None:
        """Service to enable an entity."""
        entity_registry = er.async_get(hass)
        for entity_id in call.data["entity_id"]:
            entity_registry.async_update_entity(
                entity_id=entity_id,
                disabled_by=None,
            )

    hass.services.async_register(
        domain=homeassistant.DOMAIN,
        service=SpookServices.ENABLE_ENTITY,
        service_func=_async_enable_entity,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
    )

    async_set_service_schema(
        hass,
        domain=homeassistant.DOMAIN,
        service=SpookServices.ENABLE_ENTITY,
        schema=services_file[SpookServices.ENABLE_ENTITY],
    )

    async def _async_hide_entity(call: ServiceCall) -> None:
        """Service to hide an entity."""
        entity_registry = er.async_get(hass)
        for entity_id in call.data["entity_id"]:
            entity_registry.async_update_entity(
                entity_id=entity_id,
                hidden_by=er.RegistryEntryHider.USER,
            )

    hass.services.async_register(
        domain=homeassistant.DOMAIN,
        service=SpookServices.HIDE_ENTITY,
        service_func=_async_hide_entity,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
    )

    async_set_service_schema(
        hass,
        domain=homeassistant.DOMAIN,
        service=SpookServices.HIDE_ENTITY,
        schema=services_file[SpookServices.HIDE_ENTITY],
    )

    async def _async_unhide_entity(call: ServiceCall) -> None:
        """Service to unhide an entity."""
        entity_registry = er.async_get(hass)
        for entity_id in call.data["entity_id"]:
            entity_registry.async_update_entity(
                entity_id=entity_id,
                hidden_by=None,
            )

    hass.services.async_register(
        domain=homeassistant.DOMAIN,
        service=SpookServices.UNHIDE_ENTITY,
        service_func=_async_unhide_entity,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
    )

    async_set_service_schema(
        hass,
        domain=homeassistant.DOMAIN,
        service=SpookServices.UNHIDE_ENTITY,
        schema=services_file[SpookServices.UNHIDE_ENTITY],
    )
