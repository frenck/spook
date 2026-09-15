"""Spook - Your homie. Action configuration entity reference extraction helpers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_ENABLED

from .const import LOGGER
from .entity_filtering import NEVER_AN_ENTITY_PREFIXES, async_get_all_services
from .template_extraction import (
    ENTITY_ID_PATTERN,
    async_extract_entities_from_template_string,
    is_template_string,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# The pattern enumerates every known domain, so it is long. This walker
# visits every value in a configuration, so compile it once.
_ENTITY_ID_RE = re.compile(rf"^{ENTITY_ID_PATTERN}$")


async def async_extract_entities_from_action_config(
    hass: HomeAssistant,
    config: dict[str, Any] | list,
    *,
    include_disabled: bool = True,
    known_services: set[str] | None = None,
    _in_sequence: bool = False,
    _in_payload: bool = False,
) -> set[str]:
    """Extract entity IDs from action configuration.

    Steps carrying ``enabled: false`` are skipped when ``include_disabled`` is
    False. Extracting twice and taking the difference tells which entities a
    configuration only references from steps that do not run.

    ``enabled`` only counts on list members, which is where steps, triggers and
    conditions live, and never below a ``data`` key. Service data is arbitrary
    payload: a dict or a list in there that happens to carry an ``enabled`` key
    of its own must not hide the entities around it.

    ``known_services`` is what tells an action name apart from an entity id,
    and building it flattens every service Home Assistant has. So it is built
    once here and handed down, rather than rebuilt for every template string
    this walks past. A caller that inspects one configuration after another
    should build it once and pass it in, or it pays for a rebuild per
    configuration.
    """
    entities = set()

    if not config:
        return entities

    if known_services is None:
        known_services = async_get_all_services(hass)

    if isinstance(config, list):
        for item in config:
            entities.update(
                await async_extract_entities_from_action_config(
                    hass,
                    item,
                    include_disabled=include_disabled,
                    known_services=known_services,
                    _in_sequence=True,
                    _in_payload=_in_payload,
                )
            )
        return entities

    if not isinstance(config, dict):
        return entities

    if (
        not include_disabled
        and _in_sequence
        and not _in_payload
        and config.get(CONF_ENABLED) is False
    ):
        return entities

    # Extract entity IDs from direct fields
    entities.update(
        await _extract_entities_from_action_fields(hass, config, known_services)
    )

    # Extract entities from target configuration
    entities.update(await _extract_entities_from_target(hass, config, known_services))

    # Extract entities from service data
    entities.update(
        await _extract_entities_from_service_data(hass, config, known_services)
    )

    # Extract from nested configs (like if/then/else, repeat, etc.)
    entities.update(
        await _extract_entities_from_nested_configs(
            hass,
            config,
            known_services,
            include_disabled=include_disabled,
            in_payload=_in_payload,
        )
    )

    return entities


async def _extract_entities_from_action_fields(
    hass: HomeAssistant, config: dict[str, Any], known_services: set[str]
) -> set[str]:
    """Extract entities from direct action fields."""
    entities = set()
    for key in ("entity_id", "device_id"):
        if key in config:
            entities.update(
                await async_extract_entities_from_value(
                    hass, config[key], known_services=known_services
                )
            )
    return entities


async def _extract_entities_from_target(
    hass: HomeAssistant, config: dict[str, Any], known_services: set[str]
) -> set[str]:
    """Extract entities from target configuration."""
    entities = set()
    if "target" in config and isinstance(config["target"], dict):
        target = config["target"]
        for key in ("entity_id", "device_id", "area_id", "label_id"):
            if key in target:
                entities.update(
                    await async_extract_entities_from_value(
                        hass, target[key], known_services=known_services
                    )
                )
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
    hass: HomeAssistant, config: dict[str, Any], known_services: set[str]
) -> set[str]:
    """Extract entities from service data."""
    entities = set()
    if "data" in config:
        data_value = config["data"]
        if isinstance(data_value, str):
            # data field is a template string itself
            entities.update(
                await async_extract_entities_from_value(
                    hass, data_value, known_services=known_services
                )
            )
        elif isinstance(data_value, dict):
            service = _get_action_service(config)
            # data field is a dictionary, process all its values
            for key, value in data_value.items():
                if _should_skip_service_data_value(service, key):
                    continue
                entities.update(
                    await async_extract_entities_from_value(
                        hass, value, known_services=known_services
                    )
                )
    return entities


async def _extract_entities_from_nested_configs(
    hass: HomeAssistant,
    config: dict[str, Any],
    known_services: set[str],
    *,
    include_disabled: bool = True,
    in_payload: bool = False,
) -> set[str]:
    """Extract entities from nested configurations."""
    entities = set()
    for key, value in config.items():
        if isinstance(value, (dict, list)):
            entities.update(
                await async_extract_entities_from_action_config(
                    hass,
                    value,
                    include_disabled=include_disabled,
                    known_services=known_services,
                    _in_payload=in_payload or key == "data",
                )
            )
    return entities


async def async_extract_entities_from_value(
    hass: HomeAssistant,
    value: Any,
    *,
    known_services: set[str] | None = None,
) -> set[str]:
    """Extract entity IDs from a configuration value.

    See `async_extract_entities_from_action_config` for what
    ``known_services`` is and why passing it in matters.
    """
    entities = set()

    if isinstance(value, str):
        # Check if it's a template string using util.is_template_string
        if is_template_string(value):
            # Process as template to extract entity references
            if known_services is None:
                known_services = async_get_all_services(hass)
            try:
                template_entities = await async_extract_entities_from_template_string(
                    hass, value, known_services
                )
                entities.update(template_entities)
            # pylint: disable-next=broad-exception-caught
            except Exception as exc:  # noqa: BLE001 - Keep broad for unexpected template issues
                LOGGER.debug(
                    "Failed to extract entities from template: %s, error: %s",
                    value,
                    exc,
                )
        elif not value.startswith(NEVER_AN_ENTITY_PREFIXES) and _ENTITY_ID_RE.match(value):
            # Check if it matches the entity ID pattern with known domains
            entities.add(value)
    elif isinstance(value, list):
        if known_services is None:
            known_services = async_get_all_services(hass)
        for item in value:
            entities.update(
                await async_extract_entities_from_value(
                    hass, item, known_services=known_services
                )
            )
    elif (
        isinstance(value, dict)
        and isinstance(value.get("entity"), str)
        and not value["entity"].startswith(NEVER_AN_ENTITY_PREFIXES)
    ):
        # Handle entity dict format like {"entity": "light.living_room"}
        entities.add(value["entity"])

    return entities
