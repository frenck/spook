"""Shared helpers for testing Spook against the device registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import attr

if TYPE_CHECKING:
    from homeassistant.helpers import device_registry as dr


def simulate_composite_split(
    device_registry: dr.DeviceRegistry,
    device: dr.DeviceEntry,
    composite_device_id: str,
) -> None:
    """Make a device look like a split of a pre-migration composite device.

    Home Assistant Core 2026.8 split devices that spanned multiple config
    entries into one device per entry, each carrying the ID of the composite
    device it came from. Only the registry migration creates that state, so
    tests fake it the way Core's own tests do: by replacing the stored entry.

    The container moved to `_devices` in Core 2026.9, where reaching it through
    `devices` is deprecated.
    """
    devices = getattr(device_registry, "_devices", device_registry.devices)
    devices[device.id] = attr.evolve(device, composite_device_id=composite_device_id)
