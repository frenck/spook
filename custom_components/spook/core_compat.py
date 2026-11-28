"""Spook - Your homie. Bridges the Home Assistant Core versions Spook supports."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, cast

from homeassistant import loader
from homeassistant.components.frontend import (
    DATA_DEFAULT_DARK_THEME,
    DATA_DEFAULT_THEME,
    DATA_THEMES,
    DATA_THEMES_STORE,
    DEFAULT_THEME,
)
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION
from homeassistant.core import callback
from homeassistant.helpers import target as target_helpers
from homeassistant.helpers.service import _load_services_file
from homeassistant.util.yaml import load_yaml_dict

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers import device_registry as dr, issue_registry as ir
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


@callback
def async_is_issue_hidden(
    issue_registry: ir.IssueRegistry,
    issue: ir.IssueEntry,
) -> bool:
    """Return if Home Assistant keeps an issue out of sight.

    Home Assistant Core 2026.11 hides the issues of a disabled config entry:
    the Repairs dashboard and the issue templates leave them out, until the
    entry is enabled again. Spook shows and counts what that dashboard shows,
    so it asks Core the same question. Before 2026.11 nothing is hidden.
    Can be replaced with `issue_registry.async_is_hidden` once Spook requires
    Core 2026.11 or later.
    """
    is_hidden: Callable[[ir.IssueEntry], bool] | None = getattr(
        issue_registry, "async_is_hidden", None
    )
    if is_hidden is None:
        return False

    return is_hidden(issue)


@callback
def async_extract_excluded_entity_ids(call: ServiceCall) -> set[str]:
    """Return the entity IDs the exclude block of an action call takes out.

    Home Assistant Core 2026.11 lets a target carry an `exclude` block, and
    subtracts it from `entity_id: all` with this helper. Before that there is
    no such block, and the schema refuses one, so nothing is ever excluded.
    Can be replaced with the target helper once Spook requires Core 2026.11 or
    later.
    """
    extract_excluded: Callable[..., set[str]] | None = getattr(
        target_helpers, "async_extract_excluded_entity_ids", None
    )
    if extract_excluded is None:
        return set()

    return extract_excluded(call.hass, target_helpers.TargetSelection(call.data))


@callback
def async_get_raw_blueprint_inputs(entity: Any) -> dict[str, Any] | None:
    """Return the configuration an automation or script was written with.

    That is the `use_blueprint` block with the inputs filled in, from before
    the blueprint was substituted into it. Home Assistant Core 2026.12 made it
    public as `raw_blueprint_inputs`, on an entity that loaded and on one that
    did not. Before that it is private, and not even under one name: a loaded
    entity keeps it as `_blueprint_inputs`, one that failed to load as
    `_raw_blueprint_inputs`. Core fills all three from the same validated
    configuration, so they hold the same thing.

    An entity that has none of them returns None, the same as one that was
    not made from a blueprint, so a rename upstream reads as "cannot tell"
    rather than as a guess.
    Can be replaced with the attribute once Spook requires Core 2026.12 or
    later.
    """
    for name in ("raw_blueprint_inputs", "_blueprint_inputs", "_raw_blueprint_inputs"):
        if hasattr(entity, name):
            return cast("dict[str, Any] | None", getattr(entity, name))

    return None


# The frontend's themes.
#
# Home Assistant has no way for an integration to add a theme: themes come
# from YAML, into one dict the frontend integration keeps for itself. Spook
# brings its own themes anyway, by writing into that dict. These functions
# are the only place Spook touches it, or the defaults next to it, and none
# of the names they use are in the frontend's `__all__`. The theme tests run
# a real `frontend.reload_themes` and a real restart, so the daily run
# against Home Assistant's development branch notices when this moves.
# Can go once the frontend integration lets an integration register a theme.


@callback
def async_get_themes(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return the frontend's themes, by name, to read and to add to.

    None when the frontend is not set up, so there is nowhere to add one.
    The frontend hands this very dict to browsers, so a theme added to it
    is in the theme picker the next time they ask for the list.
    """
    return hass.data.get(DATA_THEMES)


@callback
def async_get_default_themes(hass: HomeAssistant) -> tuple[str, str | None]:
    """Return the default light and dark theme, as the frontend holds them now.

    The light one is `default` for the frontend's own look. The dark one is
    None when there is none, and the light one is used in dark mode too.
    """
    return (
        hass.data.get(DATA_DEFAULT_THEME, DEFAULT_THEME),
        hass.data.get(DATA_DEFAULT_DARK_THEME),
    )


@callback
def async_set_default_themes(hass: HomeAssistant, light: str, dark: str | None) -> None:
    """Set the default light and dark theme, in memory only.

    Not stored: what the frontend stored is what somebody picked, and that
    is exactly what Spook puts back here. Browsers hear of it with the next
    `themes_updated` event, which is the caller's to fire.
    """
    hass.data[DATA_DEFAULT_THEME] = light
    hass.data[DATA_DEFAULT_DARK_THEME] = dark


async def async_load_stored_default_themes(
    hass: HomeAssistant,
) -> tuple[str | None, str | None]:
    """Return the default light and dark theme the frontend has stored.

    At startup the frontend drops a stored default it does not know yet,
    in memory, and keeps the stored one as it was. A theme Spook brings is
    not known yet then, so this is where the pick is still to be found.
    """
    if (store := hass.data.get(DATA_THEMES_STORE)) is None:
        return None, None

    stored = await store.async_load()
    if not isinstance(stored, dict):
        return None, None

    return stored.get(DATA_DEFAULT_THEME), stored.get(DATA_DEFAULT_DARK_THEME)
