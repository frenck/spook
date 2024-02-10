"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import automation
from homeassistant.const import (
    CONF_CHOOSE,
    CONF_DEFAULT,
    CONF_ELSE,
    CONF_ENABLED,
    CONF_PARALLEL,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_THEN,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from collections.abc import Sequence


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced services in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_service_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
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
        known_services = {
            f"{domain}.{service}"
            for domain, services in self.hass.services.async_services().items()
            for service in services
        }

        possible_issue_ids: set[str] = set()
        for entity in entity_component.entities:
            possible_issue_ids.add(entity.entity_id)

            if isinstance(entity, automation.UnavailableAutomationEntity):
                continue

            called_services: set[str] = set()
            _async_find_services_in_sequence(
                called_services, entity.action_script.sequence
            )

            if unknown_services := {
                service.lower()
                for service in called_services - known_services
                if isinstance(service, str) and service
            }:
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
                self._issues.add(entity.entity_id)
                LOGGER.debug(
                    (
                        "Spook found unknown service calls in %s "
                        "and created an issue for it; Services: %s",
                    ),
                    entity.entity_id,
                    ", ".join(unknown_services),
                )
            else:
                self.async_delete_issue(entity.entity_id)
                self._issues.discard(entity.entity_id)

        # Remove issues that no longer exist
        for issue_id in self._issues - possible_issue_ids:
            self.async_delete_issue(issue_id)
            self._issues.discard(issue_id)


@callback
def _async_find_services_in_sequence(  # noqa: C901
    called_services: set[str],
    sequence: Sequence[dict[str, Any]],
) -> None:
    """Find all services called in a sequence."""
    for step in sequence:
        action = cv.determine_script_action(step)

        if action == cv.SCRIPT_ACTION_CALL_SERVICE and step.get(CONF_ENABLED, True):
            called_services.add(step[CONF_SERVICE])

        if action == cv.SCRIPT_ACTION_CHOOSE:
            for choice in step[CONF_CHOOSE]:
                _async_find_services_in_sequence(called_services, choice[CONF_SEQUENCE])
            if nested_sequence := step.get(CONF_DEFAULT):
                _async_find_services_in_sequence(called_services, nested_sequence)

        if action == cv.SCRIPT_ACTION_IF:
            _async_find_services_in_sequence(called_services, step[CONF_THEN])
            if nested_sequence := step.get(CONF_ELSE):
                _async_find_services_in_sequence(called_services, nested_sequence)

        if action == cv.SCRIPT_ACTION_PARALLEL:
            for nested_sequence in step[CONF_PARALLEL]:
                _async_find_services_in_sequence(
                    called_services, nested_sequence[CONF_SEQUENCE]
                )

        if action == cv.SCRIPT_ACTION_REPEAT:
            _async_find_services_in_sequence(called_services, step[CONF_SEQUENCE])
