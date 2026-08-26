"""Spook - Your homie. Bridges the Home Assistant Core versions Spook supports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback

if TYPE_CHECKING:
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
def async_get_child_devices(device_registry: dr.DeviceRegistry) -> list[Any]:
    """Return all child devices in the device registry.

    Child devices arrived in Home Assistant Core 2026.9. They are devices in
    their own right and can be targeted like any other device. Core 2026.8 has
    no child devices at all.
    Can be removed once Spook requires Core 2026.9 or later.
    """
    return list(getattr(device_registry, "child_devices", ()))


@callback
def async_get_child_device_ids(device_registry: dr.DeviceRegistry) -> set[str]:
    """Return the IDs of all child devices in the device registry."""
    return {
        child_device.id for child_device in async_get_child_devices(device_registry)
    }


@callback
def async_get_child_devices_for_parent(
    device_registry: dr.DeviceRegistry,
    parent_device_id: str,
) -> list[Any]:
    """Return the child devices of a device."""
    return [
        child_device
        for child_device in async_get_child_devices(device_registry)
        if child_device.parent_device_id == parent_device_id
    ]


@callback
def async_is_child_device(device: Any) -> bool:
    """Return if a device entry is a child device.

    A child device names the device it belongs to, and nothing else carries
    that attribute. Child devices arrived in Home Assistant Core 2026.9, so on
    2026.8 nothing is one.
    Can be reduced to an isinstance check on `dr.ChildDeviceEntry` once Spook
    requires Core 2026.9 or later.
    """
    return getattr(device, "parent_device_id", None) is not None


@callback
def async_update_any_device(
    device_registry: dr.DeviceRegistry,
    device_id: str,
    **changes: Any,
) -> None:
    """Update a device, whether it is a device or a child device.

    Home Assistant Core 2026.9 gave child devices their own update method, and
    refuses a child device ID in `async_update_device`. Pass only changes both
    methods take: `area_id`, `disabled_by`, `labels`, `name` and
    `name_by_user`.

    An unknown device ID is left to the registry to complain about, the way it
    did before child devices existed.
    """
    if async_is_child_device(device_registry.async_get(device_id)):
        device_registry.async_update_child_device(device_id, **changes)
        return

    device_registry.async_update_device(device_id, **changes)
