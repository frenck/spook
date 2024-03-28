"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import script
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_entity_ids, async_get_all_entity_ids


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced entity in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        if self.domain not in self.hass.data[DATA_INSTANCES]:
            return

        entity_component: EntityComponent[script.ScriptEntity] = self.hass.data[
            DATA_INSTANCES
        ][self.domain]

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass, include_all_none=True)

        for entity in entity_component.entities:
            self.possible_issue_ids.add(entity.entity_id)
            if not isinstance(entity, script.UnavailableScriptEntity) and (
                unknown_entities := async_filter_known_entity_ids(
                    self.hass,
                    entity_ids=entity.script.referenced_entities,
                    known_entity_ids=known_entity_ids,
                )
            ):
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "entities": "\n".join(
                            f"- `{entity_id}`" for entity_id in unknown_entities
                        ),
                        "script": entity.name,
                        "edit": f"/config/script/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown entities in %s and created an issue "
                        "for it; Entities: %s",
                    ),
                    entity.entity_id,
                    ", ".join(unknown_entities),
                )
