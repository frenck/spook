"""Spook - Your homie. Bridges the Home Assistant Core versions Spook supports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.helpers import device_registry as dr


@callback
def async_get_device_entries(
    device_registry: dr.DeviceRegistry,
) -> list[dr.DeviceEntry]:
    """Return all device entries in the device registry.

    Home Assistant Core 2026.9 deprecated using `device_registry.devices` as a
    mapping; iterating it yields the device entries there. On 2026.8 it is
    still a mapping, so iterating yields the device IDs instead.
    Can be removed once Spook requires Core 2026.9 or later.
    """
    devices = device_registry.devices
    if isinstance(devices, Mapping):
        return list(devices.values())

    return list(devices)


@callback
def async_get_child_device_ids(device_registry: dr.DeviceRegistry) -> set[str]:
    """Return the IDs of all child devices in the device registry.

    Child devices arrived in Home Assistant Core 2026.9. They are devices in
    their own right and can be targeted like any other device. Core 2026.8 has
    no child devices at all.
    Can be removed once Spook requires Core 2026.9 or later.
    """
    child_devices: Iterable[Any] = getattr(device_registry, "child_devices", ())
    return {child_device.id for child_device in child_devices}
