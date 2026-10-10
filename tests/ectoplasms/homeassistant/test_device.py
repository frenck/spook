"""Tests for the device walks behind the Home Assistant device services.

The Core the tests pin has no child devices, so the registry is mocked here to
build the trees that only exist on Home Assistant Core 2026.9 and later. The
walk over regular devices is covered against the real registry in the device
service tests.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryDisabler

from custom_components.spook.ectoplasms.homeassistant.device import (
    async_disable_device_and_parent_if_needed,
    async_enable_device_and_parent,
)


def mock_device(device_id: str, *, via_device_id: str | None = None) -> Any:
    """Return a device that is connected through another device, or nothing."""
    return SimpleNamespace(id=device_id, disabled_by=None, via_device_id=via_device_id)


def mock_child_device(device_id: str, *, parent_device_id: str) -> Any:
    """Return a child device of a device.

    A child device has no `via_device_id` at all, so reaching for one raises
    here instead of quietly answering nothing.
    """
    return SimpleNamespace(
        id=device_id, disabled_by=None, parent_device_id=parent_device_id
    )


class MockDeviceRegistry:
    """Mock of a device registry that has child devices.

    Devices iterate as entries, child devices live in their own collection,
    and each kind has its own update method, the way Home Assistant Core
    2026.9 and later hand them out.
    """

    def __init__(self, *, devices: list[Any], child_devices: list[Any]) -> None:
        """Initialize the registry with the devices it holds."""
        self.devices = devices
        self.child_devices = child_devices
        self.updates: list[tuple[str, str]] = []

    def async_get(self, device_id: str) -> Any:
        """Return the device or child device with this ID."""
        for device in (*self.devices, *self.child_devices):
            if device.id == device_id:
                return device

        return None

    def async_update_device(self, device_id: str, **changes: Any) -> None:
        """Update a device."""
        self._apply("device", device_id, changes)

    def async_update_child_device(self, device_id: str, **changes: Any) -> None:
        """Update a child device."""
        self._apply("child_device", device_id, changes)

    def _apply(self, kind: str, device_id: str, changes: dict[str, Any]) -> None:
        """Record the update and apply it to the device."""
        self.updates.append((kind, device_id))
        device = self.async_get(device_id)
        for name, value in changes.items():
            setattr(device, name, value)


def test_disabling_a_child_device_disables_its_parent() -> None:
    """Test disabling the last child device of a device disables that device."""
    parent = mock_device("a-device")
    child = mock_child_device("a-child-device", parent_device_id=parent.id)
    device_registry = MockDeviceRegistry(devices=[parent], child_devices=[child])

    async_disable_device_and_parent_if_needed(device_registry, child.id)

    assert child.disabled_by is DeviceEntryDisabler.USER
    assert parent.disabled_by is DeviceEntryDisabler.USER
    assert device_registry.updates == [
        ("child_device", child.id),
        ("device", parent.id),
    ]


def test_disabling_one_of_two_child_devices_keeps_the_parent_enabled() -> None:
    """Test a device with another enabled child device stays enabled."""
    parent = mock_device("a-device")
    child = mock_child_device("a-child-device", parent_device_id=parent.id)
    other_child = mock_child_device("another-child-device", parent_device_id=parent.id)
    device_registry = MockDeviceRegistry(
        devices=[parent], child_devices=[child, other_child]
    )

    async_disable_device_and_parent_if_needed(device_registry, child.id)

    assert child.disabled_by is DeviceEntryDisabler.USER
    assert other_child.disabled_by is None
    assert parent.disabled_by is None


def test_a_connected_device_keeps_the_parent_of_a_child_device_enabled() -> None:
    """Test both kinds of device hanging off a device count as its children.

    A device can be the parent of child devices and the device others are
    connected through at the same time. Disabling the last child device while
    a connected device is still enabled leaves nothing to clean up.
    """
    parent = mock_device("a-device")
    connected = mock_device("a-connected-device", via_device_id=parent.id)
    child = mock_child_device("a-child-device", parent_device_id=parent.id)
    device_registry = MockDeviceRegistry(
        devices=[parent, connected], child_devices=[child]
    )

    async_disable_device_and_parent_if_needed(device_registry, child.id)

    assert parent.disabled_by is None

    async_disable_device_and_parent_if_needed(device_registry, connected.id)

    assert connected.disabled_by is DeviceEntryDisabler.USER
    assert parent.disabled_by is DeviceEntryDisabler.USER


def test_enabling_a_child_device_enables_the_parent_first() -> None:
    """Test a child device is enabled after its parent device.

    Home Assistant Core refuses to enable a child device while its parent is
    disabled, so the order is not just cosmetic.
    """
    parent = mock_device("a-device")
    parent.disabled_by = DeviceEntryDisabler.USER
    child = mock_child_device("a-child-device", parent_device_id=parent.id)
    child.disabled_by = DeviceEntryDisabler.USER
    device_registry = MockDeviceRegistry(devices=[parent], child_devices=[child])

    async_enable_device_and_parent(device_registry, child.id)

    assert parent.disabled_by is None
    assert child.disabled_by is None
    assert device_registry.updates == [
        ("device", parent.id),
        ("child_device", child.id),
    ]
