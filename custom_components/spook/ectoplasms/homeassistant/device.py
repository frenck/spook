"""Device service helpers."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr


def async_disable_device_and_parent_if_needed(
    device_registry: dr.DeviceRegistry,
    device_id: str,
) -> None:
    """Disable a device and its parent when no enabled child devices remain."""
    device = device_registry.async_update_device(
        device_id=device_id,
        disabled_by=dr.DeviceEntryDisabler.USER,
    )
    if device is None or device.via_device_id is None:
        return

    if all(
        child.disabled_by is not None
        for child in device_registry.devices.values()
        if child.via_device_id == device.via_device_id
    ):
        async_disable_device_and_parent_if_needed(
            device_registry,
            device.via_device_id,
        )


def async_enable_device_and_parent(
    device_registry: dr.DeviceRegistry,
    device_id: str,
) -> None:
    """Enable a device and its parent device chain."""
    device = device_registry.async_update_device(
        device_id=device_id,
        disabled_by=None,
    )
    if device is None or device.via_device_id is None:
        return

    async_enable_device_and_parent(device_registry, device.via_device_id)
