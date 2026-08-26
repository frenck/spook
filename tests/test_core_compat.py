"""Tests for the Home Assistant Core compatibility helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.core_compat import (
    async_get_child_device_ids,
    async_get_child_devices_for_parent,
    async_get_device_entries,
    async_is_child_device,
    async_update_any_device,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry as dr


class MockDeviceContainerView:
    """Mock of the container view Core 2026.9 and later hand out.

    It iterates as device entries, while every mapping access on it is
    deprecated. This one refuses those instead of warning, so a helper that
    still reaches for one fails the test.
    """

    def __init__(self, devices: list[Any]) -> None:
        """Initialize the view."""
        self._devices = devices

    def __iter__(self) -> Iterator[Any]:
        """Iterate over the device entries."""
        return iter(self._devices)

    def __getattr__(self, name: str) -> Any:
        """Refuse the deprecated mapping access."""
        message = f"Deprecated `device_registry.devices.{name}` access"
        raise AssertionError(message)


def test_device_entries_are_read_by_iterating() -> None:
    """Test devices are read the way Core 2026.9 and later want them read."""
    device = SimpleNamespace(id="a-device")
    device_registry = SimpleNamespace(devices=MockDeviceContainerView([device]))

    assert async_get_device_entries(device_registry) == [device]


def test_device_entries_are_read_from_a_mapping(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test devices are read as entries, not as IDs.

    Core 2026.8 still hands out the container itself, which iterates over
    device IDs instead of over device entries.
    """
    entry = MockConfigEntry(domain="test", title="Test")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", "device")},
    )

    assert async_get_device_entries(device_registry) == [device]


def test_child_device_ids_are_returned() -> None:
    """Test child devices are picked up on Core 2026.9 and later."""
    device_registry = SimpleNamespace(
        child_devices=[SimpleNamespace(id="a-child-device")]
    )

    assert async_get_child_device_ids(device_registry) == {"a-child-device"}


def test_child_device_ids_without_child_devices(
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a registry without child devices yields none.

    Core 2026.8 has no child devices at all.
    """
    assert async_get_child_device_ids(device_registry) == set()


class MockUpdateRegistry:
    """Mock of the device registry, recording how a device was updated.

    Core 2026.9 and later have a separate update method for child devices, and
    refuse a child device ID in the regular one.
    """

    def __init__(self, device: Any) -> None:
        """Initialize the registry with the one device it knows."""
        self._device = device
        self.updates: list[tuple[str, str, dict[str, Any]]] = []

    def async_get(self, device_id: str) -> Any:
        """Return the device, if it is the one this registry knows."""
        return self._device if device_id == self._device.id else None

    def async_update_device(self, device_id: str, **changes: Any) -> None:
        """Record an update of a device."""
        self.updates.append(("device", device_id, changes))

    def async_update_child_device(self, device_id: str, **changes: Any) -> None:
        """Record an update of a child device."""
        self.updates.append(("child_device", device_id, changes))


def test_a_device_is_a_child_device_when_it_has_a_parent() -> None:
    """Test child devices are told apart from devices and from nothing."""
    assert async_is_child_device(SimpleNamespace(parent_device_id="a-device")) is True
    assert async_is_child_device(SimpleNamespace(via_device_id="a-device")) is False
    assert async_is_child_device(None) is False


def test_a_child_device_is_updated_as_a_child_device() -> None:
    """Test a child device is updated through the method Core wants for it."""
    device_registry = MockUpdateRegistry(
        SimpleNamespace(id="a-child-device", parent_device_id="a-device")
    )

    async_update_any_device(device_registry, "a-child-device", area_id="an-area")

    assert device_registry.updates == [
        ("child_device", "a-child-device", {"area_id": "an-area"})
    ]


def test_a_device_is_updated_as_a_device() -> None:
    """Test anything that is not a child device takes the regular method."""
    device_registry = MockUpdateRegistry(
        SimpleNamespace(id="a-device", via_device_id=None)
    )

    async_update_any_device(device_registry, "a-device", area_id="an-area")

    assert device_registry.updates == [("device", "a-device", {"area_id": "an-area"})]


def test_child_devices_are_looked_up_by_parent() -> None:
    """Test only the child devices of the parent asked for come back."""
    child_device = SimpleNamespace(id="a-child-device", parent_device_id="a-device")
    device_registry = SimpleNamespace(
        child_devices=[
            child_device,
            SimpleNamespace(
                id="another-child-device", parent_device_id="another-device"
            ),
        ]
    )

    assert async_get_child_devices_for_parent(device_registry, "a-device") == [
        child_device
    ]


def test_an_unknown_device_is_left_to_the_registry(
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test an unknown device ID is not quietly swallowed."""
    with pytest.raises(KeyError):
        async_update_any_device(device_registry, "not-a-device", area_id=None)


def test_a_registered_device_is_updated(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device in the registry is updated for real."""
    entry = MockConfigEntry(domain="test", title="Test")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", "device")},
    )

    async_update_any_device(device_registry, device.id, labels={"a-label"})

    assert device_registry.async_get(device.id).labels == {"a-label"}
