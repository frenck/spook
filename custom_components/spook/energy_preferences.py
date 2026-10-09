"""Spook - Your homie. Unknown entities in the energy settings, and taking them out.

Home Assistant does not check what is written into the energy settings. A
battery without the meter for what goes in, or a grid connection with nothing
left on it, goes into storage as it is and breaks the energy dashboard. So
taking an entity out is done per setting, in the way that setting allows.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.energy.validate import async_validate

from .statistics_sources import async_known_to_home_assistant

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant

# The energy validation issue type raised when a referenced entity or
# statistic has no state at all: it was removed. Other issue types
# (unavailable, non-numeric, undefined statistics) are transient or are
# configuration choices rather than stale references.
_MISSING_ISSUE_TYPE = "entity_not_defined"


# Settings that can say "none": a price or a cost goes, the meter stays.
_CLEARABLE = (
    "stat_cost",
    "stat_compensation",
    "entity_energy_price",
    "entity_energy_price_export",
)
# Settings that can be left out altogether.
_OPTIONAL = ("stat_rate", "stat_soc", "included_in_stat")
# What a grid connection holds for each way the energy goes, in the unified
# form. Without its meter, the price of that way means nothing either.
_GRID_IMPORT = ("stat_energy_from", "stat_cost", "entity_energy_price")
_GRID_IMPORT_NUMBER = "number_energy_price"
_GRID_EXPORT = ("stat_energy_to", "stat_compensation", "entity_energy_price_export")
_GRID_EXPORT_NUMBER = "number_energy_price_export"


async def _async_entity_settings(hass: HomeAssistant) -> set[str]:
    """Return the energy settings that name an entity, not a statistic.

    The settings say which is which by their own names: a key beginning
    `stat_` holds a statistic ID and one beginning `entity_` holds an entity
    that has to be there, because its value is read live while the dashboard
    adds things up.
    """
    preferences = (await async_get_manager(hass)).data or {}

    return {
        value
        for group in preferences.values()
        if isinstance(group, list)
        for source in group
        if isinstance(source, dict)
        for key, value in source.items()
        if key.startswith("entity_") and isinstance(value, str)
    }


async def async_unknown_energy_entities(hass: HomeAssistant) -> set[str]:
    """Return what the energy settings name that Home Assistant does not know."""
    validation = await async_validate(hass)
    unknown: set[str] = set()
    for issues_group in (
        validation.energy_sources,
        validation.device_consumption,
        validation.device_consumption_water,
    ):
        for issues in issues_group:
            if (issue := issues.issues.get(_MISSING_ISSUE_TYPE)) is not None:
                unknown.update(
                    affected for affected, _detail in issue.affected_entities
                )

    # Home Assistant reports "entity not defined" for anything it cannot find
    # a state for, and having no state covers more than being unknown: an
    # integration that has not finished setting up, an entity somebody
    # disabled, and an energy source fed by statistics that were published
    # straight into the recorder without an entity ever existing. The energy
    # dashboard draws that last one perfectly happily. Telling somebody their
    # working gas meter is unknown is a repair for a problem they do not have.
    # #1565.
    #
    # Not for a price, though. A price is read off the state as the dashboard
    # works, so statistics recorded under the same name do not make one work
    # and letting it off would hide a setting that is broken.
    unknown -= await async_known_to_home_assistant(
        hass,
        unknown - await _async_entity_settings(hass),
    )
    return unknown


def _without_power(setting: dict[str, Any], unknown: set[str]) -> None:
    """Drop power settings that lean on something unknown, in place.

    Home Assistant works the power sensor out of `power_config`, and writes
    the result into `stat_rate`. One without the other is no power setting.
    """
    if any(value in unknown for value in (setting.get("power_config") or {}).values()):
        setting.pop("power_config", None)
        setting.pop("stat_rate", None)


def _without_unknown(setting: dict[str, Any], unknown: set[str]) -> None:
    """Clear the prices and drop the extras that name something unknown."""
    for key in _CLEARABLE:
        if setting.get(key) in unknown:
            setting[key] = None
    for key in _OPTIONAL:
        if setting.get(key) in unknown:
            del setting[key]
    _without_power(setting, unknown)


def _legacy_grid(source: dict[str, Any], unknown: set[str]) -> dict[str, Any] | None:
    """Return a grid connection in the older form, without what is unknown."""
    flows = {
        "flow_from": "stat_energy_from",
        "flow_to": "stat_energy_to",
    }
    for flow_key, meter_key in flows.items():
        kept = []
        for flow in source.get(flow_key) or []:
            if flow.get(meter_key) in unknown:
                continue
            _without_unknown(flow, unknown)
            kept.append(flow)
        source[flow_key] = kept

    if "power" in source:
        kept_power = []
        for power in source["power"] or []:
            if power.get("stat_rate") in unknown:
                continue
            _without_power(power, unknown)
            if "stat_rate" in power or "power_config" in power:
                kept_power.append(power)
        source["power"] = kept_power

    if not (source["flow_from"] or source["flow_to"] or source.get("power")):
        return None
    return source


def _unified_grid(source: dict[str, Any], unknown: set[str]) -> dict[str, Any] | None:
    """Return a grid connection in the unified form, without what is unknown."""
    if source.get("stat_energy_from") in unknown:
        source.update(dict.fromkeys((*_GRID_IMPORT, _GRID_IMPORT_NUMBER)))
    if source.get("stat_energy_to") in unknown:
        source.update(dict.fromkeys((*_GRID_EXPORT, _GRID_EXPORT_NUMBER)))
    _without_unknown(source, unknown)

    if not (
        source.get("stat_energy_from")
        or source.get("stat_energy_to")
        or source.get("stat_rate")
        or source.get("power_config")
    ):
        return None
    return source


def _source(source: dict[str, Any], unknown: set[str]) -> dict[str, Any] | None:
    """Return an energy source without what is unknown, or None to drop it."""
    if source.get("type") == "grid":
        if "flow_from" in source or "flow_to" in source:
            return _legacy_grid(source, unknown)
        return _unified_grid(source, unknown)

    # Solar, battery, gas and water cannot do without their meters. A battery
    # missing either of its two is no battery the dashboard can draw.
    if any(
        source.get(meter) in unknown for meter in ("stat_energy_from", "stat_energy_to")
    ):
        return None

    _without_unknown(source, unknown)
    return source


def _devices(devices: list[dict[str, Any]], unknown: set[str]) -> list[dict[str, Any]]:
    """Return the devices without what is unknown.

    A device whose consumption is unknown goes. One that said it is part of
    such a device would then point at nothing, so it stops saying so.
    """
    dropped = {
        device.get("stat_consumption")
        for device in devices
        if device.get("stat_consumption") in unknown
    }
    kept = []
    for device in devices:
        if device.get("stat_consumption") in dropped:
            continue
        _without_unknown(device, unknown | dropped)
        kept.append(device)
    return kept


def energy_preferences_without(
    preferences: Mapping[str, Any],
    unknown: set[str],
) -> dict[str, Any]:
    """Return the parts of the energy settings, without what is unknown.

    Only the parts the settings have are returned, ready to hand to the
    energy manager as an update. The settings passed in are left alone.
    """
    cleaned: dict[str, Any] = {}

    if "energy_sources" in preferences:
        sources = (
            _source(copy.deepcopy(source), unknown)
            for source in preferences["energy_sources"]
        )
        cleaned["energy_sources"] = [source for source in sources if source]

    for key in ("device_consumption", "device_consumption_water"):
        if key in preferences:
            cleaned[key] = _devices(copy.deepcopy(preferences[key]), unknown)

    return cleaned
