"""Tests for the homeassistant enable_device and disable_device services."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceEntryDisabler

from custom_components.spook.ectoplasms.homeassistant.services import (
    disable_device,
    enable_device,
)

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceRegistry

    from tests.common import MockUser
    from pytest_homeassistant.typing import WebSocketGenerator


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


@pytest.fixture
def disabled_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a disabled config entry for test devices.

    Devices it owns are disabled by the config entry, which is the only
    consistent way to reach that disable reason since Home Assistant 2026.8.
    """
    entry = MockConfigEntry(
        domain="test",
        title="Disabled test",
        disabled_by=ConfigEntryDisabler.USER,
    )
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
        via_device_id=parent.id,
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
    disabled_config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test disabling a child device does not override the parent disable reason."""
    grandparent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "grandparent-device")},
    )
    parent = device_registry.async_get_or_create(
        config_entry_id=disabled_config_entry.entry_id,
        identifiers={("test", "parent-device")},
        via_device_id=grandparent.id,
    )

    assert parent.disabled_by is DeviceEntryDisabler.CONFIG_ENTRY

    child = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "child-device")},
        via_device_id=parent.id,
    )

    await hass.services.async_call(
        DOMAIN,
        "disable_device",
        {"device_id": child.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert device_registry.async_get(child.id).disabled_by is DeviceEntryDisabler.USER
    assert (
        device_registry.async_get(parent.id).disabled_by
        is DeviceEntryDisabler.CONFIG_ENTRY
    )
    assert (
        device_registry.async_get(grandparent.id).disabled_by
        is DeviceEntryDisabler.USER
    )


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
        via_device_id=parent.id,
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "sibling-device")},
        via_device_id=parent.id,
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
        via_device_id=parent.id,
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


@pytest.mark.usefixtures("device_services")
async def test_device_services_survive_via_device_cycle(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test the device services on two devices forming a via_device cycle."""
    first = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "cycle-first-device")},
    )
    second = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "cycle-second-device")},
    )
    device_registry.async_update_device(device_id=first.id, via_device_id=second.id)
    device_registry.async_update_device(device_id=second.id, via_device_id=first.id)

    await hass.services.async_call(
        DOMAIN,
        "disable_device",
        {"device_id": first.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert device_registry.async_get(first.id).disabled_by is DeviceEntryDisabler.USER
    assert device_registry.async_get(second.id).disabled_by is DeviceEntryDisabler.USER

    await hass.services.async_call(
        DOMAIN,
        "enable_device",
        {"device_id": first.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert device_registry.async_get(first.id).disabled_by is None
    assert device_registry.async_get(second.id).disabled_by is None


@pytest.mark.usefixtures("device_services")
async def test_enable_device_service_refuses_device_disabled_by_its_entry(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    disabled_config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test enabling a device says so when its integration entry keeps it off.

    Home Assistant ignores the enable, so the action would do nothing without
    a word. The refusal comes before anything is written: the device that
    could have been enabled stays as it was. #2082.
    """
    disabled_by_user = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "disabled-by-user")},
        disabled_by=DeviceEntryDisabler.USER,
    )
    disabled_by_entry = device_registry.async_get_or_create(
        config_entry_id=disabled_config_entry.entry_id,
        identifiers={("test", "disabled-by-entry")},
    )

    assert disabled_by_entry.disabled_by is DeviceEntryDisabler.CONFIG_ENTRY

    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            DOMAIN,
            "enable_device",
            {"device_id": [disabled_by_user.id, disabled_by_entry.id]},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )

    assert raised.value.translation_key == "device_disabled_by_integration_entry"
    assert raised.value.translation_placeholders == {
        "device_id": disabled_by_entry.id,
        "entry": "Disabled test",
    }
    assert (
        device_registry.async_get(disabled_by_user.id).disabled_by
        is DeviceEntryDisabler.USER
    )
    assert (
        device_registry.async_get(disabled_by_entry.id).disabled_by
        is DeviceEntryDisabler.CONFIG_ENTRY
    )


@pytest.mark.usefixtures("device_services")
async def test_enable_device_service_refuses_whatever_disabled_the_device(
    hass: HomeAssistant,
    disabled_config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the refusal goes by the integration entry, not by the device.

    A device disabled by hand keeps saying so when its integration entry is
    disabled after it. Home Assistant ignores enabling that one just as well.
    """
    device = device_registry.async_get_or_create(
        config_entry_id=disabled_config_entry.entry_id,
        identifiers={("test", "disabled-by-hand")},
        disabled_by=DeviceEntryDisabler.USER,
    )

    assert device.disabled_by is DeviceEntryDisabler.USER

    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            DOMAIN,
            "enable_device",
            {"device_id": device.id},
            blocking=True,
        )

    assert raised.value.translation_key == "device_disabled_by_integration_entry"
    assert device_registry.async_get(device.id).disabled_by is DeviceEntryDisabler.USER
    assert "sets disabled_by to None" not in caplog.text


@pytest.mark.usefixtures("device_services")
async def test_enable_device_service_refuses_child_of_device_disabled_by_its_entry(
    hass: HomeAssistant,
    disabled_config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a child device is refused along with the parent it belongs to.

    A child device lives on the integration entry of its parent, so the
    disabled entry that keeps the parent off keeps the child off as well.
    """
    parent = device_registry.async_get_or_create(
        config_entry_id=disabled_config_entry.entry_id,
        identifiers={("test", "parent-device")},
    )
    child = device_registry.async_get_or_create_child(
        config_entry_id=disabled_config_entry.entry_id,
        identifiers={("test", "child-device")},
        parent_device_id=parent.id,
    )

    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            DOMAIN,
            "enable_device",
            {"device_id": child.id},
            blocking=True,
        )

    assert raised.value.translation_placeholders == {
        "device_id": child.id,
        "entry": "Disabled test",
    }
    assert device_registry.async_get(child.id).disabled
    assert device_registry.async_get(parent.id).disabled
    assert "sets disabled_by to None" not in caplog.text


@pytest.mark.usefixtures("device_services")
async def test_enable_device_service_says_why_in_the_frontend(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    disabled_config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test the frontend shows which entry to enable, not "Unknown error".

    The frontend runs an action through `execute_script`, which only passes
    the message on for a validation error.
    """
    device = device_registry.async_get_or_create(
        config_entry_id=disabled_config_entry.entry_id,
        identifiers={("test", "disabled-by-entry")},
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "execute_script",
            "sequence": [
                {
                    "action": "homeassistant.enable_device",
                    "data": {"device_id": device.id},
                }
            ],
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "service_validation_error"
    assert (
        response["error"]["translation_key"] == "device_disabled_by_integration_entry"
    )
    assert response["error"]["translation_placeholders"] == {
        "device_id": device.id,
        "entry": "Disabled test",
    }


@pytest.mark.parametrize("parent_disabled_by", [None, DeviceEntryDisabler.USER])
@pytest.mark.usefixtures("device_services")
async def test_enable_device_service_leaves_parent_its_entry_keeps_disabled(
    hass: HomeAssistant,
    disabled_config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    parent_disabled_by: DeviceEntryDisabler | None,
) -> None:
    """Test enabling a device passes over a parent only its entry can enable.

    The device asked for is enabled. The one it is connected through stays
    off with its integration entry, whether it was disabled by hand before
    or not, without Home Assistant having to ignore an enable that could not
    work.
    """
    # Leaving the reason out is not the same as passing none: that would ask
    # for an enabled device on a disabled entry.
    reason = {"disabled_by": parent_disabled_by} if parent_disabled_by else {}
    parent = device_registry.async_get_or_create(
        config_entry_id=disabled_config_entry.entry_id,
        identifiers={("test", "parent-device")},
        **reason,
    )
    enabled_config_entry = MockConfigEntry(domain="test", title="Test")
    enabled_config_entry.add_to_hass(hass)
    child = device_registry.async_get_or_create(
        config_entry_id=enabled_config_entry.entry_id,
        identifiers={("test", "child-device")},
        disabled_by=DeviceEntryDisabler.USER,
        via_device_id=parent.id,
    )

    await hass.services.async_call(
        DOMAIN,
        "enable_device",
        {"device_id": child.id},
        blocking=True,
    )

    assert device_registry.async_get(child.id).disabled_by is None
    assert device_registry.async_get(parent.id).disabled_by is (
        parent_disabled_by or DeviceEntryDisabler.CONFIG_ENTRY
    )
    assert "sets disabled_by to None" not in caplog.text
