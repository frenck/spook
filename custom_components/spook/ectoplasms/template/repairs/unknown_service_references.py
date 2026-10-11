"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.const import (
    CONF_ACTIONS,
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)

from ....const import LOGGER
from ....entity_filtering import (
    async_filter_known_services,
    async_get_all_services,
    async_name_helper_in_the_registry,
    find_services_in_helper_options,
)
from ....repairs import AbstractSpookRepair
from ..configuration import (
    EVENT_TEMPLATE_RELOADED,
    async_get_yaml_template_entities,
    async_is_current,
    own_configuration,
)


def _action_lists(config: dict[str, Any]) -> dict[str, Any]:
    """Return the actions a template entity from YAML runs.

    Home Assistant validates every action of a template entity, like a
    switch's `turn_on`, into a list of steps. A mapping is something else,
    like its attributes: a single step is a mapping too, so one with an
    `action` key would pass for a call it never makes. A trigger based
    entity also runs the actions of its section.
    """
    actions = {
        key: value
        for key, value in own_configuration(config).items()
        if isinstance(value, list)
    }
    if CONF_ACTIONS in config:
        actions[CONF_ACTIONS] = config[CONF_ACTIONS]
    return actions


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds unknown actions referenced in template entities.

    Template helpers keep their actions in the config entry options.
    Template entities from the `template:` section of the configuration are
    read from the entities themselves.
    """

    domain = "template"
    repair = "template_unknown_service_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
        EVENT_TEMPLATE_RELOADED,
    }
    # Any integration, not just template: whether an action counts as missing
    # depends on whether the integration providing it is disabled, and that
    # can change without an action coming or going.
    inspect_config_entry_changed = True
    inspect_on_reload = "template"
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Inspect template helper and entity actions for unavailable services."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_services = async_get_all_services(self.hass)

        for entry in self.hass.config_entries.async_entries(self.domain):
            self.possible_issue_ids.add(entry.entry_id)

            services = find_services_in_helper_options(entry.options)

            unknown_services = async_filter_known_services(
                self.hass,
                services=services,
                known_services=known_services,
            )
            if not unknown_services:
                continue

            self.async_create_issue(
                issue_id=entry.entry_id,
                references=unknown_services,
                translation_placeholders={
                    "helper": entry.title,
                    "entity_id": async_name_helper_in_the_registry(
                        self.hass, entry.entry_id
                    ),
                    "edit": "/config/helpers",
                    "services": _listed(unknown_services),
                },
            )

        for template_entity in async_get_yaml_template_entities(self.hass):
            # Validating actions is CPU-bound, and there can be many template
            # entities: the event loop gets a turn before each.
            await asyncio.sleep(0)
            self.possible_issue_ids.add(template_entity.entity_id)

            # A template entity reloaded during that turn may say something
            # else entirely, and the reload starts another round that looks
            # at that.
            if not async_is_current(self.hass, template_entity):
                continue

            unknown_services = async_filter_known_services(
                self.hass,
                services=find_services_in_helper_options(
                    _action_lists(template_entity.config)
                ),
                known_services=known_services,
            )
            if not unknown_services:
                continue

            self.async_create_issue(
                issue_id=template_entity.entity_id,
                references=unknown_services,
                # There is no editor for YAML, so the issue says where to look.
                translation_key=f"{self.repair}_yaml",
                translation_placeholders={
                    "name": template_entity.name,
                    "entity_id": template_entity.entity_id,
                    "services": _listed(unknown_services),
                },
            )


def _listed(services: set[str]) -> str:
    """Return the actions as a list for the issue."""
    return "\n".join(f"- `{service}`" for service in sorted(services))
