"""Device helpers for Home Assistant services."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr

from ...core_compat import async_get_device_entries


@callback
def async_disable_device_and_parent_if_needed(
    device_registry: dr.DeviceRegistry,
    device_id: str,
) -> None:
    """Disable a device and its parent when no enabled child devices remain."""
    # A registry can contain via_device_id cycles (including self-references),
    # so track visited devices to avoid walking the chain forever.
    seen: set[str] = set()
    current_id: str | None = device_id
    while current_id is not None and current_id not in seen:
        seen.add(current_id)
        device = device_registry.async_get(current_id)
        if device is None:
            return

        if device.disabled_by is None:
            device_registry.async_update_device(
                device_id=current_id,
                disabled_by=dr.DeviceEntryDisabler.USER,
            )

        if device.via_device_id is None:
            return

        if not all(
            child.id == current_id or child.disabled_by is not None
            for child in async_get_device_entries(device_registry)
            if child.via_device_id == device.via_device_id
        ):
            return

        current_id = device.via_device_id


@callback
def async_enable_device_and_parent(
    device_registry: dr.DeviceRegistry,
    device_id: str,
) -> None:
    """Enable a device and its parent device chain."""
    # A registry can contain via_device_id cycles (including self-references),
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
        current_id = device.via_device_id

    # Enable parents before their children, like the previous recursive walk
    for chain_device_id in reversed(chain):
        device_registry.async_update_device(
            device_id=chain_device_id,
            disabled_by=None,
        )
