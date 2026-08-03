"""Spook - Your homie. Action configuration entity reference extraction helpers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .const import LOGGER
from .template_extraction import (
    ENTITY_ID_PATTERN,
    async_extract_entities_from_template_string,
    is_template_string,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


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
