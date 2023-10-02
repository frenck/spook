"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components.homeassistant import scene
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import valid_entity_id
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....repairs import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown entities in scenes."""

    domain = "scene"
    repair = "scene_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        scene.EVENT_SCENE_RELOADED,
        "event_group_reloaded",
        "event_integration_reloaded",
        "event_mqtt_reloaded",
    }

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        entity_ids = {
            entity.entity_id for entity in self.entity_registry.entities.values()
        }.union(self.hass.states.async_entity_ids())

        scenes: list[scene.HomeAssistantScene] = self.hass.data[
            "homeassistant_scene"
        ].entities.values()

        for entity in scenes:
            if unknown_entities := {
                entity_id
                for entity_id in entity.scene_config.states
                if (entity_id not in entity_ids and valid_entity_id(entity_id))
            }:
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "entities": "\n".join(
                            f"- `{entity_id}`" for entity_id in unknown_entities
                        ),
                        "scene": entity.name,
                        "entity_id": entity.entity_id,
                        "edit": f"/config/scene/edit/{entity.unique_id}",
                    },
                )
                LOGGER.debug(
                    "Spook found unknown entities references in %s "
                    "and created an issue for it; Entities: %s",
                    entity.entity_id,
                    ", ".join(unknown_entities),
                )
            else:
                self.async_delete_issue(entity.entity_id)
