"""Spook - Your homie."""

from __future__ import annotations

from typing import Any

from homeassistant.components import script
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_entity_ids, async_get_all_entity_ids


def extract_entities_from_trigger_config(config: dict[str, Any] | list) -> set[str]:
    """Extract entity IDs from a trigger config."""
    entities = set()

    if not config:
        return entities

    if isinstance(config, list):
        for item in config:
            entities.update(extract_entities_from_trigger_config(item))
        return entities

    if not isinstance(config, dict):
        return entities

    # Extract entity_id from trigger config
    if "entity_id" in config:
        entity_id = config["entity_id"]
        if isinstance(entity_id, str):
            entities.add(entity_id)
        elif isinstance(entity_id, list):
            entities.update([e for e in entity_id if isinstance(e, str)])

    # Recursively process nested configs
    for value in config.values():
        if isinstance(value, (dict, list)):
            entities.update(extract_entities_from_trigger_config(value))

    return entities


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

    def _get_blueprint_trigger_entities(self, entity: script.ScriptEntity) -> set[str]:
        """Extract entity references from blueprint trigger inputs."""
        entities = set()

        if (
            not hasattr(entity, "referenced_blueprint")
            or not entity.referenced_blueprint
        ):
            return entities

        config = getattr(entity, "_config", None)
        if not config or not isinstance(config, dict) or "use_blueprint" not in config:
            return entities

        blueprint_config = config["use_blueprint"]
        if "input" not in blueprint_config:
            return entities

        input_config = blueprint_config["input"]
        # Look for inputs that might contain triggers (like discard_when)
        for key, value in input_config.items():
            if isinstance(value, (dict, list)) and "trigger" in str(value):
                trigger_entities = extract_entities_from_trigger_config(value)
                if trigger_entities:
                    LOGGER.debug(
                        "Found entities in blueprint trigger input '%s': %s",
                        key,
                        trigger_entities,
                    )
                    entities.update(trigger_entities)

        return entities

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
            if isinstance(entity, script.UnavailableScriptEntity):
                continue

            # Get all referenced entities from the script
            referenced_entities = set(entity.script.referenced_entities)

            # Check for blueprint trigger inputs
            blueprint_entities = self._get_blueprint_trigger_entities(entity)
            referenced_entities.update(blueprint_entities)

            # Check for unknown entities
            if unknown_entities := async_filter_known_entity_ids(
                self.hass,
                entity_ids=referenced_entities,
                known_entity_ids=known_entity_ids,
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
