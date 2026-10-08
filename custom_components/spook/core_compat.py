"""Spook - Your homie. Bridges the Home Assistant Core versions Spook supports."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, cast

from homeassistant import loader
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION
from homeassistant.core import callback
from homeassistant.helpers.service import _load_services_file
from homeassistant.util.yaml import load_yaml_dict

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry as dr
    from homeassistant.loader import Integration

# From here, a service description registered in code has its target validated
# again (home-assistant/core#180556).
_TARGETS_VALIDATED_AGAIN = (2026, 10)


def load_service_descriptions(integration: Integration) -> dict[str, Any]:
    """Return an integration's services.yaml, the way Core takes it in code.

    Home Assistant's own loader validates each target, which turns
    `supported_features` into the numbers they stand for. Up to Core 2026.9
    that is the form a description registered in code has to be in. From
    2026.10 that description is validated once more, which only takes a
    target as written: handed the numbers, Core warns and leaves the target
    out, and the action's entity picker then offers every entity there is.
    Once Spook requires Core 2026.10 or later, the targets are always the
    written ones and the version check can go.
    """
    descriptions = cast("dict[str, Any]", _load_services_file(integration))
    if (MAJOR_VERSION, MINOR_VERSION) < _TARGETS_VALIDATED_AGAIN:
        return descriptions

    written = load_yaml_dict(str(integration.file_path / "services.yaml"))
    for key, description in descriptions.items():
        # Read off the same file, so the two always agree. Should they ever
        # not, the loaded target stays: setting up has to survive it, since
        # failing here would take every one of Spook's actions down with it.
        written_description = written.get(key) or {}
        if description and "target" in description and "target" in written_description:
            description["target"] = written_description["target"]

    return descriptions


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


@callback
def async_clear_custom_components_cache(hass: HomeAssistant) -> None:
    """Make the loader look in custom_components again.

    The loader scans that folder once and keeps the list, so a sub
    integration linked in after that stays unknown to it. Dropping the list
    makes the next lookup scan again. Core 2026.11 has a helper for this,
    which the Marketplace uses to load an integration straight after
    installing it. Before that, the helper is no more than the pop below.
    Can be replaced with the loader helper once Spook requires Core 2026.11 or
    later.
    """
    clear_cache: Callable[[HomeAssistant], None] | None = getattr(
        loader, "async_clear_custom_components_cache", None
    )
    if clear_cache is not None:
        clear_cache(hass)
        return

    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)
