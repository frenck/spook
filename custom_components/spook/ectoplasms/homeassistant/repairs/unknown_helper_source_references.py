"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


# Helper integrations that store one or more source entity references in
# their config entry options, mapped to the option keys holding them. A
# value is either an entity ID or an entity registry ID (both resolved via
# ``er.async_resolve_entity_id``); a key may hold a single value or a list.
#
# Deliberately excluded: ``group`` (already covered by the group unknown
# members repair) and the helpers with their own source repairs
# (``integration``, ``switch_as_x``, ``trend``, ``utility_meter``).
SOURCE_OPTION_KEYS: dict[str, tuple[str, ...]] = {
    "derivative": ("source",),
    "filter": ("entity_id",),
    "generic_hygrostat": ("target_sensor", "humidifier"),
    "generic_thermostat": ("target_sensor", "heater"),
    "history_stats": ("entity_id",),
    "min_max": ("entity_ids",),
    "mold_indicator": (
        "indoor_temp_sensor",
        "indoor_humidity_sensor",
        "outdoor_temp_sensor",
    ),
    "statistics": ("entity_id",),
    "threshold": ("entity_id",),
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

    # Bayesian nests each source under an observation.
    if entry.domain == "bayesian":
        for observation in entry.options.get("observations", []):
            if isinstance(observation, dict) and isinstance(
                entity_id := observation.get("entity_id"), str
            ):
                values.add(entity_id)

    return values


class SpookRepair(AbstractSpookRepair):
    """Spook repair that finds helpers referencing unknown source entities.

    Reads config entry options directly (a public API), so it also covers
    helpers whose entity failed to set up, and avoids the private entity
    attributes the per-helper source repairs rely on.
    """

    domain = "homeassistant"
    repair = "unknown_helper_source_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True

    automatically_clean_up_issues = True

    #: Helper domains this repair inspects.
    _inspected_domains = frozenset({*SOURCE_OPTION_KEYS, "bayesian"})

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        self.possible_issue_ids.clear()

        known_entity_ids = async_get_all_entity_ids(self.hass)
        entity_registry = er.async_get(self.hass)

        for entry in self.hass.config_entries.async_entries():
            if entry.domain not in self._inspected_domains:
                continue

            self.possible_issue_ids.add(entry.entry_id)

            unknown: set[str] = set()
            for value in _source_values(entry):
                resolved = er.async_resolve_entity_id(entity_registry, value)
                if resolved is None:
                    # A registry ID whose entry was deleted.
                    unknown.add(value)
                else:
                    unknown.update(
                        async_filter_known_entity_ids(
                            self.hass,
                            [resolved],
                            known_entity_ids=known_entity_ids,
                        )
                    )

            if not unknown:
                continue

            self.async_create_issue(
                issue_id=entry.entry_id,
                issue_domain=entry.domain,
                translation_placeholders={
                    "helper": entry.title,
                    "domain": entry.domain,
                    "sources": "\n".join(f"- `{source}`" for source in sorted(unknown)),
                },
            )
