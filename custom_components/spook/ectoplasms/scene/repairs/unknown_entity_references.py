"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_entity_ids, async_get_all_entity_ids

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

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        # Check if Home Assistant scenes are loaded
        if "homeassistant_scene" not in self.hass.data:
            return

        scenes: list[scene.HomeAssistantScene] = self.hass.data[
            "homeassistant_scene"
        ].entities.values()

        known_entity_ids = async_get_all_entity_ids(self.hass)

        for entity in scenes:
            self.possible_issue_ids.add(entity.entity_id)
            if unknown_entities := async_filter_known_entity_ids(
                self.hass,
                entity_ids=entity.scene_config.states,
                known_entity_ids=known_entity_ids,
            ):
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
