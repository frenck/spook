"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import automation
from homeassistant.helpers import label_registry as lr
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_label_ids, async_get_all_label_ids


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced labels in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_label_references"
    inspect_events = {
        lr.EVENT_LABEL_REGISTRY_UPDATED,
    }
    inspect_on_reload = True

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        if self.domain not in self.hass.data[DATA_INSTANCES]:
            return

        entity_component: EntityComponent[automation.AutomationEntity] = self.hass.data[
            DATA_INSTANCES
        ][self.domain]

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_label_ids = async_get_all_label_ids(self.hass)

        for entity in entity_component.entities:
            self.possible_issue_ids.add(entity.entity_id)
            if not isinstance(entity, automation.UnavailableAutomationEntity) and (
                unknown_labels := async_filter_known_label_ids(
                    self.hass,
                    label_ids=entity.referenced_labels,
                    known_label_ids=known_label_ids,
                )
            ):
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "labels": "\n".join(f"- `{label}`" for label in unknown_labels),
                        "automation": entity.name,
                        "edit": f"/config/automation/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown labels in %s "
                        "and created an issue for it; Labels: %s",
                    ),
                    entity.entity_id,
                    ", ".join(unknown_labels),
                )
