"""Tests for the homeassistant enable_device and disable_device services."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryDisabler

from custom_components.spook.ectoplasms.homeassistant.services import (
    disable_device,
    enable_device,
)

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceRegistry

    from tests.common import MockUser


@pytest.fixture
def device_services(hass: HomeAssistant) -> None:
    """Register the Spook device services."""
    hass.config.components.add(DOMAIN)
    enable_device.SpookService(hass).async_register()
    disable_device.SpookService(hass).async_register()


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry for test devices."""
    entry = MockConfigEntry(domain="test", title="Test")
    entry.add_to_hass(hass)
    return entry


@pytest.mark.usefixtures("device_services")
async def test_enable_device_service_enables_disabled_device(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test the enable device service enables a disabled device."""
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "target-device")},
        disabled_by=DeviceEntryDisabler.USER,
    )

    assert device.disabled_by is DeviceEntryDisabler.USER

    await hass.services.async_call(
        DOMAIN,
        "enable_device",
        {"device_id": device.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert device_registry.async_get(device.id).disabled_by is None


@pytest.mark.usefixtures("device_services")
async def test_device_services_accept_multiple_devices(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test the device services accept multiple device IDs."""
    devices = [
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("test", "first-device")},
        ),
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("test", "second-device")},
        ),
    ]

    await hass.services.async_call(
        DOMAIN,
        "disable_device",
        {"device_id": [device.id for device in devices]},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert all(
        device_registry.async_get(device.id).disabled_by is DeviceEntryDisabler.USER
        for device in devices
    )

    await hass.services.async_call(
        DOMAIN,
        "enable_device",
        {"device_id": [device.id for device in devices]},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert all(
        device_registry.async_get(device.id).disabled_by is None for device in devices
    )


@pytest.mark.usefixtures("device_services")
async def test_disable_device_service_disables_parent_without_other_children(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test disabling a child device also disables its parent device."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "parent-device")},
    )
    child = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "child-device")},
        via_device=("test", "parent-device"),
    )

    await hass.services.async_call(
        DOMAIN,
        "disable_device",
        {"device_id": child.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert device_registry.async_get(child.id).disabled_by is DeviceEntryDisabler.USER
    assert device_registry.async_get(parent.id).disabled_by is DeviceEntryDisabler.USER


@pytest.mark.usefixtures("device_services")
async def test_disable_device_service_preserves_parent_disabled_reason(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test disabling a child device does not override the parent disable reason."""
    grandparent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "grandparent-device")},
    )
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "parent-device")},
        disabled_by=DeviceEntryDisabler.CONFIG_ENTRY,
        via_device=("test", "grandparent-device"),
    )
    child = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "child-device")},
        via_device=("test", "parent-device"),
    )

    await hass.services.async_call(
        DOMAIN,
        "disable_device",
        {"device_id": child.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert device_registry.async_get(child.id).disabled_by is DeviceEntryDisabler.USER
    assert device_registry.async_get(parent.id).disabled_by is DeviceEntryDisabler.CONFIG_ENTRY
    assert device_registry.async_get(grandparent.id).disabled_by is DeviceEntryDisabler.USER


@pytest.mark.usefixtures("device_services")
async def test_disable_device_service_keeps_parent_enabled_with_enabled_children(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test disabling one child device keeps a parent with enabled children enabled."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "parent-device")},
    )
    child = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "child-device")},
        via_device=("test", "parent-device"),
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "sibling-device")},
        via_device=("test", "parent-device"),
    )

    await hass.services.async_call(
        DOMAIN,
        "disable_device",
        {"device_id": child.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert device_registry.async_get(child.id).disabled_by is DeviceEntryDisabler.USER
    assert device_registry.async_get(parent.id).disabled_by is None


@pytest.mark.usefixtures("device_services")
async def test_enable_device_service_enables_parent_device(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test enabling a child device also enables its parent device."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "parent-device")},
        disabled_by=DeviceEntryDisabler.USER,
    )
    child = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "child-device")},
        disabled_by=DeviceEntryDisabler.USER,
        via_device=("test", "parent-device"),
    )

    await hass.services.async_call(
        DOMAIN,
        "enable_device",
        {"device_id": child.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert device_registry.async_get(child.id).disabled_by is None
    assert device_registry.async_get(parent.id).disabled_by is None
