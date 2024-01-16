"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components import automation
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced areas in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_area_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
    }

    _issues: set[str] = set()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        if self.domain not in self.hass.data[DATA_INSTANCES]:
            return

        entity_component: EntityComponent[automation.AutomationEntity] = self.hass.data[
            DATA_INSTANCES
        ][self.domain]

        LOGGER.debug("Spook is inspecting: %s", self.repair)
        areas = set(self.area_registry.areas)
        possible_issue_ids: set[str] = set()
        for entity in entity_component.entities:
            possible_issue_ids.add(entity.entity_id)
            if not isinstance(entity, automation.UnavailableAutomationEntity) and (
                unknown_areas := {
                    area
                    for area in entity.referenced_areas - areas
                    if isinstance(area, str)
                }
            ):
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "areas": "\n".join(f"- `{area}`" for area in unknown_areas),
                        "automation": entity.name,
                        "edit": f"/config/automation/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                self._issues.add(entity.entity_id)
                LOGGER.debug(
                    (
                        "Spook found unknown areas in %s "
                        "and created an issue for it; Areas: %s",
                    ),
                    entity.entity_id,
                    ", ".join(unknown_areas),
                )
            else:
                self.async_delete_issue(entity.entity_id)
                self._issues.discard(entity.entity_id)

        # Remove issues for entities that no longer exist
        for issue_id in self._issues - possible_issue_ids:
            self.async_delete_issue(issue_id)
            self._issues.discard(issue_id)
