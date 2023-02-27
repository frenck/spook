"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components import automation
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from . import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced areas in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_area_references"
    events = {automation.EVENT_AUTOMATION_RELOADED, ar.EVENT_AREA_REGISTRY_UPDATED}

    _entity_component: EntityComponent[automation.AutomationEntity]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._entity_component = self.hass.data[DATA_INSTANCES][self.domain]
        await super().async_activate()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        areas = set(self.area_registry.areas)
        for entity in self._entity_component.entities:
            if unknown_areas := entity.referenced_areas - areas:
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "areas": [f"- `{area}`\n" for area in unknown_areas],
                        "automation": entity.name,
                        "edit": f"/config/automation/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
            else:
                self.async_delete_issue(entity.entity_id)
