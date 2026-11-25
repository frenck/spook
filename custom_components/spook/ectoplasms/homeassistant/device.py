"""Device helpers for Home Assistant services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr

from ...core_compat import (
    async_get_child_devices_for_parent,
    async_get_device_entries,
    async_is_child_device,
    async_update_any_device,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


@callback
def _async_get_parent_device_id(device: Any) -> str | None:
    """Return the device a device hangs off, if it hangs off one at all.

    A child device names its parent device, everything else names the device
    it is connected through.
    """
    if async_is_child_device(device):
        return device.parent_device_id

    return device.via_device_id


@callback
def _async_get_devices_hanging_off(
    device_registry: dr.DeviceRegistry,
    device_id: str,
) -> list[Any]:
    """Return the devices that hang off a device.

    A device can be the parent of child devices and the device others are
    connected through at the same time. Both hang off it.
    """
    return [
        *async_get_child_devices_for_parent(device_registry, device_id),
        *(
            device
            for device in async_get_device_entries(device_registry)
            if device.via_device_id == device_id
        ),
    ]


@callback
def async_disable_device_and_parent_if_needed(
    device_registry: dr.DeviceRegistry,
    device_id: str,
) -> None:
    """Disable a device and its parent when nothing enabled hangs off it."""
    # A registry can contain via_device_id cycles between distinct devices,
    # so track visited devices to avoid walking the chain forever.
    seen: set[str] = set()
    current_id: str | None = device_id
    while current_id is not None and current_id not in seen:
        seen.add(current_id)
        device = device_registry.async_get(current_id)
        if device is None:
            return

        if device.disabled_by is None:
            async_update_any_device(
                device_registry,
                current_id,
                disabled_by=dr.DeviceEntryDisabler.USER,
            )

        parent_id = _async_get_parent_device_id(device)
        if parent_id is None:
            return

        if not all(
            hanging_device.id == current_id or hanging_device.disabled_by is not None
            for hanging_device in _async_get_devices_hanging_off(
                device_registry, parent_id
            )
        ):
            return

        current_id = parent_id


@callback
def async_enable_device_and_parent(
    device_registry: dr.DeviceRegistry,
    device_id: str,
) -> None:
    """Enable a device and its parent device chain."""
    # A registry can contain via_device_id cycles between distinct devices,
    # so track visited devices to avoid walking the chain forever.
    chain: list[str] = []
    seen: set[str] = set()
    current_id: str | None = device_id
    while current_id is not None and current_id not in seen:
        device = device_registry.async_get(current_id)
        if device is None:
            break
        seen.add(current_id)
        chain.append(current_id)
        current_id = _async_get_parent_device_id(device)

    # Enable parents before their children, like the previous recursive walk.
    # Home Assistant Core refuses to enable a child device while its parent is
    # disabled, so the order is not just cosmetic.
    for chain_device_id in reversed(chain):
        # Home Assistant ignores enabling a device its integration entry
        # keeps off, and is to refuse it outright, so it is left alone.
        if async_get_entry_keeping_device_disabled(device_registry, chain_device_id):
            continue

        async_update_any_device(device_registry, chain_device_id, disabled_by=None)


@callback
def async_get_entry_keeping_device_disabled(
    device_registry: dr.DeviceRegistry,
    device_id: str,
) -> ConfigEntry | None:
    """Return the disabled integration entry that keeps a device disabled.

    A device cannot be enabled while its integration entry is disabled,
    whatever disabled the device itself: one disabled by hand before its
    entry was, keeps saying so. A child device lives on the integration
    entry of its parent device, so this covers the parent being off too.
    """
    if (device := device_registry.async_get(device_id)) is None:
        return None

    # A device lives on one integration entry. Older Home Assistant Core
    # versions let it belong to several, and named a primary one.
    entry_id = getattr(device, "config_entry_id", None) or getattr(
        device, "primary_config_entry", None
    )
    if entry_id is None:
        return None

    entry = device_registry.hass.config_entries.async_get_entry(entry_id)
    if entry is None or not entry.disabled_by:
        return None

    return entry
