"""Spook - Your homie."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair

# Spelled out rather than imported: reading a bridge's options is all this
# needs, and importing HomeKit itself pulls in its HomeKit library.
_FILTER = "filter"
_INCLUDE_ENTITIES = "include_entities"
_EXCLUDE_ENTITIES = "exclude_entities"


class SpookRepair(AbstractSpookRepair):
    """Spook repair that finds HomeKit bridges naming entities that are gone.

    HomeKit keeps the entity IDs it was given, and does not follow a rename.
    An included entity renamed or removed drops out of the Home app without a
    word, and an excluded one renamed shows up in it.
    """

    domain = "homekit"
    repair = "homekit_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = "homekit"
    inspect_on_entity_added_or_removed = True

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass)

        # A disabled bridge bridges nothing, so what it names is moot.
        for entry in self.hass.config_entries.async_entries(
            self.domain, include_ignore=False, include_disabled=False
        ):
            self.possible_issue_ids.add(entry.entry_id)

            entity_filter = entry.options.get(_FILTER)
            if not isinstance(entity_filter, dict):
                continue

            unknown_included = self._unknown_in(
                entity_filter.get(_INCLUDE_ENTITIES), known_entity_ids
            )
            unknown_excluded = self._unknown_in(
                entity_filter.get(_EXCLUDE_ENTITIES), known_entity_ids
            )
            if not unknown_included and not unknown_excluded:
                continue

            descriptions = []
            if unknown_included:
                descriptions.append(
                    await async_describe_unknown_entities(
                        self.hass, sorted(unknown_included)
                    )
                )
            if unknown_excluded:
                descriptions.append(
                    await async_describe_unknown_entities(
                        self.hass, sorted(unknown_excluded), note="excluded"
                    )
                )

            # A bridge from YAML takes its options from there, and HomeKit's
            # own options flow turns it away.
            self.async_create_issue(
                issue_id=entry.entry_id,
                translation_key=(
                    f"{self.repair}_yaml"
                    if entry.source == SOURCE_IMPORT
                    else self.repair
                ),
                # Excluded ones carry their role along. Moving an entity from
                # one list to the other turns the warning around, and an
                # "ignore" given to the one is no answer to the other.
                references=unknown_included
                | {f"excluded:{entity_id}" for entity_id in unknown_excluded},
                translation_placeholders={
                    "bridge": entry.title,
                    "entities": "\n".join(descriptions),
                },
            )
            LOGGER.debug(
                "Spook found unknown entities in HomeKit bridge %s "
                "and created an issue for it; Entities: %s",
                entry.title,
                ", ".join(sorted(unknown_included | unknown_excluded)),
            )

    def _unknown_in(self, entity_ids: Any, known_entity_ids: set[str]) -> set[str]:
        """Return the entity IDs in a filter list that are unknown."""
        if not isinstance(entity_ids, list):
            return set()

        return async_filter_known_entity_ids(
            self.hass,
            entity_ids={item for item in entity_ids if isinstance(item, str)},
            known_entity_ids=known_entity_ids,
        )
