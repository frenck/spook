"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import valid_entity_id
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from homeassistant.components.homeassistant import scene


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown entities in scenes."""

    domain = "scene"
    repair = "scene_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_on_reload = True

    _issues: set[str] = set()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        # Check if Home Assistant scenes are loaded
        if "homeassistant_scene" not in self.hass.data:
            return

        entity_ids = {
            entity.entity_id for entity in self.entity_registry.entities.values()
        }.union(self.hass.states.async_entity_ids())

        scenes: list[scene.HomeAssistantScene] = self.hass.data[
            "homeassistant_scene"
        ].entities.values()

        possible_issue_ids: set[str] = set()
        for entity in scenes:
            possible_issue_ids.add(entity.entity_id)
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
                self._issues.add(entity.entity_id)
                LOGGER.debug(
                    "Spook found unknown entities references in %s "
                    "and created an issue for it; Entities: %s",
                    entity.entity_id,
                    ", ".join(unknown_entities),
                )
            else:
                self.async_delete_issue(entity.entity_id)
                self._issues.discard(entity.entity_id)

        # Remove issues that are no longer valid
        for issue_id in self._issues - possible_issue_ids:
            self.async_delete_issue(issue_id)
            self._issues.discard(issue_id)
