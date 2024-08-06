"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import automation
from homeassistant.const import (
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import (
    async_filter_known_services,
    async_find_services_in_sequence,
    async_get_all_services,
)


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced services in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_service_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
    }
    inspect_config_entry_changed = True
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

        known_services = async_get_all_services(self.hass)

        for entity in entity_component.entities:
            self.possible_issue_ids.add(entity.entity_id)

            if isinstance(entity, automation.UnavailableAutomationEntity):
                continue

            if unknown_services := async_filter_known_services(
                self.hass,
                services=async_find_services_in_sequence(entity.action_script.sequence),
                known_services=known_services,
            ):
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "services": "\n".join(
                            f"- `{service}`" for service in unknown_services
                        ),
                        "automation": entity.name,
                        "edit": f"/config/automation/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown action calls in %s "
                        "and created an issue for it; Actions: %s",
                    ),
                    entity.entity_id,
                    ", ".join(unknown_services),
                )
