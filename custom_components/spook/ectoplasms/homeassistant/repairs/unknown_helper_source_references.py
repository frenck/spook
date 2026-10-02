"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....helper_sources import SOURCE_OPTION_KEYS, async_unknown_helper_sources
from ....repairs import AbstractSpookRepair


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

        for entry in self.hass.config_entries.async_entries():
            if entry.domain not in self._inspected_domains:
                continue

            self.possible_issue_ids.add(entry.entry_id)

            unknown = async_unknown_helper_sources(self.hass, entry)
            if not unknown:
                continue

            sources = "\n".join(f"- `{source}`" for source in sorted(unknown))
            self.async_create_issue(
                issue_id=entry.entry_id,
                references=unknown,
                issue_domain=entry.domain,
                is_fixable=True,
                data={
                    "helper_config_entry_id": entry.entry_id,
                    # What the fix checks again before removing the helper.
                    "helper_unknown_sources": ",".join(sorted(unknown)),
                    "helper": entry.title,
                    "domain": entry.domain,
                    "sources": sources,
                },
                translation_placeholders={
                    "helper": entry.title,
                    "domain": entry.domain,
                    "sources": sources,
                },
            )
