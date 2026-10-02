"""Spook - Your homie. Finding the sources a helper has lost."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er

from .entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

# In one place because two things ask it and they must not drift: the repair
# that reports a helper's missing sources, and the fix that acts on them. A
# fix working from a different answer than the report would remove something
# nobody was shown.

# Helper integrations that store one or more source entity references in
# their config entry options, mapped to the option keys holding them. A
# value is either an entity ID or an entity registry ID (both resolved via
# ``er.async_resolve_entity_id``); a key may hold a single value or a list.
#
# Deliberately excluded: ``group`` (covered by the group unknown members
# repair) and ``min_max`` (covered by the min_max unknown sources repair,
# which can prune the missing members).
SOURCE_OPTION_KEYS: dict[str, tuple[str, ...]] = {
    "derivative": ("source",),
    "filter": ("entity_id",),
    "generic_hygrostat": ("target_sensor", "humidifier"),
    "generic_thermostat": ("target_sensor", "heater"),
    "history_stats": ("entity_id",),
    "integration": ("source",),
    "mold_indicator": (
        "indoor_temp_sensor",
        "indoor_humidity_sensor",
        "outdoor_temp_sensor",
    ),
    "statistics": ("entity_id",),
    "switch_as_x": ("entity_id",),
    "threshold": ("entity_id",),
    "trend": ("entity_id",),
    "utility_meter": ("source",),
}


def _source_values(entry: ConfigEntry) -> set[str]:
    """Return the raw source references stored on a helper config entry."""
    values: set[str] = set()
    for key in SOURCE_OPTION_KEYS.get(entry.domain, ()):
        raw = entry.options.get(key)
        if isinstance(raw, str):
            values.add(raw)
        elif isinstance(raw, list):
            values.update(item for item in raw if isinstance(item, str))

    # Bayesian stores each observation as a config subentry.
    if entry.domain == "bayesian":
        for subentry in entry.subentries.values():
            if isinstance(entity_id := subentry.data.get("entity_id"), str):
                values.add(entity_id)

    return values


# The min/max helper stores its members under this option key, as entity
# registry IDs or entity IDs (both resolved via ``er.async_resolve_entity_id``).
MIN_MAX_ENTITY_IDS = "entity_ids"


def async_helper_sources(entry: ConfigEntry) -> set[str]:
    """Return every source reference a helper is configured with."""
    return _source_values(entry)


def async_unknown_helper_sources(hass: HomeAssistant, entry: ConfigEntry) -> set[str]:
    """Return the raw source references of a helper that are gone."""
    return _async_unknown(hass, _source_values(entry), as_written=False)


def async_unknown_min_max_members(hass: HomeAssistant, entry: ConfigEntry) -> set[str]:
    """Return the raw member references of a min/max helper that are gone."""
    return _async_unknown(
        hass,
        (
            value
            for value in entry.options.get(MIN_MAX_ENTITY_IDS) or []
            if isinstance(value, str)
        ),
        as_written=True,
    )


def _async_unknown(
    hass: HomeAssistant,
    values: Iterable[str],
    *,
    as_written: bool,
) -> set[str]:
    """Return which of these references point at nothing.

    `as_written` is whether a reference that resolves is named the way the
    helper stores it, or by the entity ID it resolves to. The two repairs
    settled on different answers before this was shared, and an issue is
    filed under what it names, so changing either would bring back every
    issue somebody had already dealt with.
    """
    entity_registry = er.async_get(hass)
    known_entity_ids = async_get_all_entity_ids(hass)

    unknown: set[str] = set()
    for value in values:
        resolved = er.async_resolve_entity_id(entity_registry, value)
        if resolved is None:
            # A registry ID whose entry was deleted.
            unknown.add(value)
        elif async_filter_known_entity_ids(
            hass, [resolved], known_entity_ids=known_entity_ids
        ):
            unknown.add(value if as_written else resolved)

    return unknown
