"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import group
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
)
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids
from ....entity_suggestions import async_describe_unknown_entities
from ....helper_sources import async_group_members
from ....repairs import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown member entities in groups."""

    domain = group.DOMAIN
    repair = "group_unknown_members"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = group.DOMAIN
    inspect_on_reload = True

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass)

        for entity, members in async_group_members(self.hass):
            self.possible_issue_ids.add(entity.entity_id)

            if unknown_entities := async_filter_known_entity_ids(
                self.hass, entity_ids=members, known_entity_ids=known_entity_ids
            ):
                described = await async_describe_unknown_entities(
                    self.hass, sorted(unknown_entities)
                )
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    references=unknown_entities,
                    is_fixable=True,
                    data={
                        "group_entity_id": entity.entity_id,
                        # What the fix checks again before dropping any.
                        "group_unknown_entity_ids": ",".join(sorted(unknown_entities)),
                        "group": entity.name,
                        "entities": described,
                    },
                    translation_placeholders={
                        "entities": described,
                        "group": entity.name,
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    "Spook found unknown member entities in %s "
                    "and created an issue for it; Entities: %s",
                    entity.entity_id,
                    ", ".join(unknown_entities),
                )
