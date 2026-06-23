"""Spook - Your homie."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from homeassistant.components import automation
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_filtering import (
    ENTITY_ID_PATTERN,
    async_extract_entities_from_config,
    async_extract_entities_from_template_string,
    async_filter_known_entity_ids_with_templates,
    async_get_all_entity_ids,
    is_template_string,
)
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def extract_template_entities_from_automation_entity(
    hass: HomeAssistant, entity: Any
) -> set[str]:
    """Extract entities from automation configuration using Template analysis.

    This function finds template strings in automation configuration and creates
    Template objects to extract entity references using Template.async_render_to_info().
    This provides more comprehensive entity detection than regex-based parsing alone.
    """
    # Get the automation configuration
    config = None
    if hasattr(entity, "raw_config") and entity.raw_config:
        config = entity.raw_config
    else:
        return set()

    return await async_extract_entities_from_config(hass, config)


async def extract_entities_from_automation_config(
    hass: HomeAssistant, config: dict[str, Any]
) -> set[str]:
    """Extract entity IDs from automation configuration."""
    entities = set()

    if not isinstance(config, dict):
        return entities

    # Extract entities from trigger config
    for key in ("trigger", "triggers"):
        if key in config:
            entities.update(
                await extract_entities_from_trigger_config(hass, config[key])
            )

    # Extract entities from condition config
    for key in ("condition", "conditions"):
        if key in config:
            entities.update(
                await extract_entities_from_condition_config(hass, config[key])
            )

    # Extract entities from action config
    for key in ("action", "actions"):
        if key in config:
            entities.update(
                await extract_entities_from_action_config(hass, config[key])
            )

    return entities


async def extract_entities_from_trigger_config(
    hass: HomeAssistant, config: dict[str, Any] | list
) -> set[str]:
    """Extract entity IDs from trigger configuration."""
    entities = set()

    if not config:
        return entities

    if isinstance(config, list):
        for item in config:
            entities.update(await extract_entities_from_trigger_config(hass, item))
        return entities

    if not isinstance(config, dict):
        return entities

    # Entity ID fields in triggers
    for key in ("entity_id", "device_id"):
        if key in config:
            entities.update(await extract_entities_from_value(hass, config[key]))

    # Zone trigger has zone field
    if "zone" in config:
        entities.update(await extract_entities_from_value(hass, config["zone"]))

    # Extract from nested configs
    for value in config.values():
        if isinstance(value, (dict, list)):
            entities.update(await extract_entities_from_trigger_config(hass, value))

    return entities


def extract_event_types_from_trigger_config(config: dict[str, Any] | list) -> set[str]:
    """Extract event types from trigger configuration."""
    event_types = set()

    if not config:
        return event_types

    if isinstance(config, list):
        for item in config:
            event_types.update(extract_event_types_from_trigger_config(item))
        return event_types

    if not isinstance(config, dict):
        return event_types

    value = config.get("event_type")
    if isinstance(value, str):
        event_types.add(value)
    elif isinstance(value, list):
        event_types.update(item for item in value if isinstance(item, str))

    for value in config.values():
        if isinstance(value, (dict, list)):
            event_types.update(extract_event_types_from_trigger_config(value))

    return event_types


async def extract_entities_from_condition_config(
    hass: HomeAssistant, config: dict[str, Any] | list
) -> set[str]:
    """Extract entity IDs from condition configuration."""
    entities = set()

    if not config:
        return entities

    if isinstance(config, list):
        for item in config:
            entities.update(await extract_entities_from_condition_config(hass, item))
        return entities

    if not isinstance(config, dict):
        return entities

    # Entity ID fields in conditions
    for key in ("entity_id", "device_id", "zone"):
        if key in config:
            entities.update(await extract_entities_from_value(hass, config[key]))

    # Extract from nested configs
    for value in config.values():
        if isinstance(value, (dict, list)):
            entities.update(await extract_entities_from_condition_config(hass, value))

    return entities


async def extract_entities_from_action_config(
    hass: HomeAssistant, config: dict[str, Any] | list
) -> set[str]:
    """Extract entity IDs from action configuration."""
    entities = set()

    if not config:
        return entities

    if isinstance(config, list):
        for item in config:
            entities.update(await extract_entities_from_action_config(hass, item))
        return entities

    if not isinstance(config, dict):
        return entities

    # Extract entity IDs from direct fields
    entities.update(await _extract_entities_from_action_fields(hass, config))

    # Extract entities from target configuration
    entities.update(await _extract_entities_from_target(hass, config))

    # Extract entities from service data
    entities.update(await _extract_entities_from_service_data(hass, config))

    # Extract from nested configs (like if/then/else, repeat, etc.)
    entities.update(await _extract_entities_from_nested_configs(hass, config))

    return entities


async def _extract_entities_from_action_fields(
    hass: HomeAssistant, config: dict[str, Any]
) -> set[str]:
    """Extract entities from direct action fields."""
    entities = set()
    for key in ("entity_id", "device_id"):
        if key in config:
            entities.update(await extract_entities_from_value(hass, config[key]))
    return entities


async def _extract_entities_from_target(
    hass: HomeAssistant, config: dict[str, Any]
) -> set[str]:
    """Extract entities from target configuration."""
    entities = set()
    if "target" in config and isinstance(config["target"], dict):
        target = config["target"]
        for key in ("entity_id", "device_id", "area_id", "label_id"):
            if key in target:
                entities.update(await extract_entities_from_value(hass, target[key]))
    return entities


def _get_action_service(config: dict[str, Any]) -> str | None:
    """Return the service/action name configured for an action."""
    service = config.get("service", config.get("action"))
    return service if isinstance(service, str) else None


def _should_skip_service_data_value(
    service: str | None,
    key: str,
) -> bool:
    """Return if a service data value should not be scanned for entity IDs."""
    return service is not None and service.startswith("notify.") and key == "target"


async def _extract_entities_from_service_data(
    hass: HomeAssistant, config: dict[str, Any]
) -> set[str]:
    """Extract entities from service data."""
    entities = set()
    if "data" in config:
        data_value = config["data"]
        if isinstance(data_value, str):
            # data field is a template string itself
            entities.update(await extract_entities_from_value(hass, data_value))
        elif isinstance(data_value, dict):
            service = _get_action_service(config)
            # data field is a dictionary, process all its values
            for key, value in data_value.items():
                if _should_skip_service_data_value(service, key):
                    continue
                entities.update(await extract_entities_from_value(hass, value))
    return entities


async def _extract_entities_from_nested_configs(
    hass: HomeAssistant, config: dict[str, Any]
) -> set[str]:
    """Extract entities from nested configurations."""
    entities = set()
    for value in config.values():
        if isinstance(value, (dict, list)):
            entities.update(await extract_entities_from_action_config(hass, value))
    return entities


async def extract_entities_from_value(hass: HomeAssistant, value: Any) -> set[str]:
    """Extract entity IDs from a configuration value."""
    entities = set()

    if isinstance(value, str):
        # Check if it's a template string using util.is_template_string
        if is_template_string(value):
            # Process as template to extract entity references
            try:
                template_entities = await async_extract_entities_from_template_string(
                    hass, value
                )
                entities.update(template_entities)
            # pylint: disable-next=broad-exception-caught
            except Exception as exc:  # noqa: BLE001 - Keep broad for unexpected template issues
                LOGGER.debug(
                    "Failed to extract entities from template: %s, error: %s",
                    value,
                    exc,
                )
        elif re.match(rf"^{ENTITY_ID_PATTERN}$", value):
            # Check if it matches the entity ID pattern with known domains
            entities.add(value)
    elif isinstance(value, list):
        for item in value:
            entities.update(await extract_entities_from_value(hass, item))
    elif (
        isinstance(value, dict)
        and "entity" in value
        and isinstance(value["entity"], str)
    ):
        # Handle entity dict format like {"entity": "light.living_room"}
        entities.add(value["entity"])

    return entities


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced entity in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "entities"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    _known_entity_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known entity IDs (including ALL/NONE) for this inspection cycle."""
        self._known_entity_ids = async_get_all_entity_ids(
            self.hass, include_all_none=True
        )

    def _should_inspect_entity(self, entity: Any) -> bool:
        """Skip disabled automations."""
        return entity.enabled

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown entity IDs referenced by ``entity`` (incl. templates)."""
        all_entities = set(entity.referenced_entities)

        # Also extract entities directly from raw configuration if available
        if hasattr(entity, "raw_config") and entity.raw_config:
            all_entities.update(
                await extract_entities_from_automation_config(
                    self.hass, entity.raw_config
                )
            )
            for key in ("trigger", "triggers"):
                all_entities.difference_update(
                    extract_event_types_from_trigger_config(entity.raw_config.get(key))
                )

        # Extract entities from Template objects within the automation entity
        all_entities.update(
            await extract_template_entities_from_automation_entity(self.hass, entity)
        )

        return await async_filter_known_entity_ids_with_templates(
            self.hass,
            entity_ids=all_entities,
            known_entity_ids=self._known_entity_ids,
        )
