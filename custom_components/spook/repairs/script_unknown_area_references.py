"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components import script
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ..const import LOGGER
from . import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced areas in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_area_references"
    events = {ar.EVENT_AREA_REGISTRY_UPDATED}

    _entity_component: EntityComponent[script.ScriptEntity]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._entity_component = self.hass.data[DATA_INSTANCES][self.domain]
        await super().async_activate()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)
        areas = set(self.area_registry.areas)
        for entity in self._entity_component.entities:
            if unknown_areas := entity.script.referenced_areas - areas:
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "areas": "\n".join(f"- `{area}`" for area in unknown_areas),
                        "script": entity.name,
                        "edit": f"/config/script/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown areas in %s "
                        "and created an issue for it; Areas: %s"
                    ),
                    entity.entity_id,
                    ", ".join(unknown_areas),
                )
            else:
                self.async_delete_issue(entity.entity_id)
