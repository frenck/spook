"""Tests for the Home Assistant Core compatibility helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.core_compat import (
    async_get_child_device_ids,
    async_get_device_entries,
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
