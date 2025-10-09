"""Spook - Your homie."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    CONF_CHOOSE,
    CONF_DEFAULT,
    CONF_ELSE,
    CONF_ENABLED,
    CONF_PARALLEL,
    CONF_REPEAT,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_THEN,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_START,
    Platform,
)
from homeassistant.core import (
    callback,
    valid_entity_id,
)
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.helpers.template import Template

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from types import ModuleType

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


# Entity domains to ignore when filtering unknown entities
IGNORED_ENTITY_DOMAINS = (
    "device_tracker.",
    "group.",
    "persistent_notification.",
    "scene.",
)

# Additional known domains that are not in the Platform enum
ADDITIONAL_DOMAINS = [
    "alert",
    "automation",
    "counter",
    "group",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "person",
    "plant",
    "proximity",
    "schedule",
    "script",
    "sun",
    "tag",
    "timer",
    "zone",
]

# Build a list of all known domains
KNOWN_DOMAINS = [platform.value for platform in Platform] + ADDITIONAL_DOMAINS

# Home Assistant core entity ID validation patterns (from homeassistant/core.py)
_OBJECT_ID = r"(?!_)[\da-z_]+(?<!_)"
# Modified _DOMAIN pattern to only match known domains
_DOMAIN = r"(?:" + "|".join(KNOWN_DOMAINS) + r")"
ENTITY_ID_PATTERN = _DOMAIN + r"\." + _OBJECT_ID

# Template function names that accept entity IDs as first parameter
_ENTITY_FUNCTIONS = [
    "states",
    "is_state",
    "state_attr",
    "is_state_attr",
    "has_value",
    "state_translated",
    "device_id",
    "device_name",
    "device_attr",
    "is_device_attr",
    "config_entry_id",
    "area_id",
    "area_name",
    "floor_id",
    "floor_name",
    "is_hidden_entity",
    "expand",
    "distance",
    "closest",
]

# Build regex patterns using Home Assistant's core validation patterns
ENTITY_ID_TEMPLATE_PATTERNS = [
    # Template functions with entity ID as first parameter
    rf"(?:{'|'.join(_ENTITY_FUNCTIONS)})\s*\(\s*['\"]({ENTITY_ID_PATTERN})['\"]",
    # Direct entity state access patterns (states.domain.entity)
    rf"states\.({_DOMAIN})\.({_OBJECT_ID})(?:\.state|\.attributes)",
    # Entity IDs in any quoted context (captures all entity IDs in lists, etc.)
    rf"['\"]({ENTITY_ID_PATTERN})['\"]",
    # Entity IDs followed by filter functions (entity_id | function)
    rf"['\"]({ENTITY_ID_PATTERN})['\"](?:\s*\|\s*(?:{'|'.join(_ENTITY_FUNCTIONS)}))",
]

_CACHED_ALL_ENTITY_IDS: set[str] | None = None
_UNSUB_CACHE_INVALIDATION: Callable[[], None] | None = None


@callback
def _clear_all_entity_ids_cache(*_args: Any) -> None:
    """Clear the cached set of all entity IDs."""
    # pylint: disable-next=global-statement
    global _CACHED_ALL_ENTITY_IDS  # noqa: PLW0603
    LOGGER.debug("Clearing all_entity_ids cache.")
    _CACHED_ALL_ENTITY_IDS = None


def async_setup_all_entity_ids_cache_invalidation(
    hass: HomeAssistant,
) -> Callable[[], None]:
    """Set up event listeners to invalidate the all_entity_ids cache.

    Returns a callable to unsubscribe the listeners.
    """
    # pylint: disable-next=global-statement
    global _UNSUB_CACHE_INVALIDATION  # noqa: PLW0603

    if _UNSUB_CACHE_INVALIDATION is not None:
        LOGGER.debug(
            "Spook's entity ID cache invalidation already set up. Skipping.",
        )
        return _UNSUB_CACHE_INVALIDATION

    LOGGER.debug("Setting up Spook's all_entity_ids cache invalidation listeners.")

    # Listen for entity registry updates
    unsub_registry_update = hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED, _clear_all_entity_ids_cache
    )
    # Listen for Home Assistant start to ensure cache is clear then
    unsub_hass_start = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START, _clear_all_entity_ids_cache
    )
    # Listen for components loading
    unsub_component_loaded = hass.bus.async_listen(
        EVENT_COMPONENT_LOADED, _clear_all_entity_ids_cache
    )

    # Perform an initial clear, just in case.
    _clear_all_entity_ids_cache()

    def _unsubscribe_listeners() -> None:
        # pylint: disable-next=global-statement
        global _UNSUB_CACHE_INVALIDATION  # noqa: PLW0603
        LOGGER.debug(
            "Unsubscribing from Spook's all_entity_ids cache invalidation listeners.",
        )
        unsub_registry_update()
        unsub_hass_start()
        unsub_component_loaded()
        _UNSUB_CACHE_INVALIDATION = None  # Mark as unsubscribed

    _UNSUB_CACHE_INVALIDATION = _unsubscribe_listeners
    return _unsubscribe_listeners


@callback
def async_get_all_entity_ids(
    hass: HomeAssistant, *, include_all_none: bool = False
) -> set[str]:
    """Return all entity IDs, known to Home Assistant, using a cache."""
    # pylint: disable-next=global-statement
    global _CACHED_ALL_ENTITY_IDS  # noqa: PLW0603

    if _CACHED_ALL_ENTITY_IDS is None:
        LOGGER.debug(
            "Spook's all_entity_ids cache is empty, populating...",
        )
        entity_registry = er.async_get(hass)
        entity_ids_from_registry = {
            entity.entity_id for entity in entity_registry.entities.values()
        }
        entity_ids_from_states = hass.states.async_entity_ids()

        combined_entity_ids = entity_ids_from_registry.union(entity_ids_from_states)

        # Filter out ignored domains
        _CACHED_ALL_ENTITY_IDS = {
            entity_id
            for entity_id in combined_entity_ids
            if not entity_id.startswith(IGNORED_ENTITY_DOMAINS)
        }
        LOGGER.debug(
            "Spook's all_entity_ids cache populated with %s entities",
            len(_CACHED_ALL_ENTITY_IDS),
        )

    # Return a copy from the cache, optionally adding ALL/NONE
    if include_all_none:
        return _CACHED_ALL_ENTITY_IDS.union({ENTITY_MATCH_ALL, ENTITY_MATCH_NONE})
    return _CACHED_ALL_ENTITY_IDS.copy()


async def async_forward_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Set up Spook ectoplasms."""
    LOGGER.debug("Setting up Spook ectoplasms")

    modules: list[ModuleType] = []

    def _load_all_ectoplasm_modules() -> None:
        """Load all Spook ectoplasm modules."""
        for module_file in Path(__file__).parent.rglob("ectoplasms/*/__init__.py"):
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace(
                "/",
                ".",
            )
            LOGGER.debug("Loading Spook ectoplasm: %s", module_path)
            module = importlib.import_module(f".{module_path}", __package__)
            if hasattr(module, "async_setup_entry"):
                modules.append(module)
                LOGGER.debug("Setting up Spook ectoplasm: %s", module_path)

    await hass.async_add_import_executor_job(_load_all_ectoplasm_modules)
    await asyncio.gather(*(module.async_setup_entry(hass, entry) for module in modules))


async def async_forward_platform_entry_setups_to_ectoplasm(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: Platform,
) -> None:
    """Set up Spook ectoplasm platform."""
    LOGGER.debug("Setting up Spook ectoplasm platform: %s", platform)

    modules: list[ModuleType] = []

    def _load_all_ectoplasm_platform_modules() -> None:
        """Load all Spook ectoplasm platform modules."""
        for module_file in Path(__file__).parent.rglob(f"ectoplasms/*/{platform}.py"):
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace(
                "/",
                ".",
            )
            LOGGER.debug("Loading Spook %s from ectoplasm: %s", platform, module_path)
            modules.append(importlib.import_module(f".{module_path}", __package__))
            LOGGER.debug("Setting up Spook ectoplasm %s: %s", platform, module_path)

    await hass.async_add_import_executor_job(_load_all_ectoplasm_platform_modules)
    await asyncio.gather(
        *(
            module.async_setup_entry(hass, entry, async_add_entities)
            for module in modules
        )
    )


def link_sub_integrations(hass: HomeAssistant) -> bool:
    """Link Spook sub integrations."""
    LOGGER.debug("Linking up Spook sub integrations")

    changes = False
    for manifest in Path(__file__).parent.rglob("integrations/*/manifest.json"):
        LOGGER.debug("Linking Spook sub integration: %s", manifest.parent.name)
        dest = Path(hass.config.config_dir) / "custom_components" / manifest.parent.name
        if not dest.exists():
            src = (
                Path(hass.config.config_dir)
                / "custom_components"
                / DOMAIN
                / "integrations"
                / manifest.parent.name
            )
            dest.symlink_to(src)
            changes = True
    return changes


def unlink_sub_integrations(hass: HomeAssistant) -> None:
    """Unlink Spook sub integrations."""
    LOGGER.debug("Unlinking Spook sub integrations")
    for manifest in Path(__file__).parent.rglob("integrations/*/manifest.json"):
        LOGGER.debug("Unlinking Spook sub integration: %s", manifest.parent.name)
        dest = Path(hass.config.config_dir) / "custom_components" / manifest.parent.name
        if dest.exists():
            dest.unlink()


@callback
def async_get_all_area_ids(hass: HomeAssistant) -> set[str]:
    """Return all area IDs, known to Home Assistant."""
    area_registry = ar.async_get(hass)
    return set(area_registry.areas)


@callback
def async_filter_known_area_ids(
    hass: HomeAssistant, *, area_ids: set[str], known_area_ids: set[str] | None = None
) -> set[str]:
    """Filter out known area IDs."""
    if known_area_ids is None:
        known_area_ids = async_get_all_area_ids(hass)
    return {
        area_id for area_id in area_ids - known_area_ids if isinstance(area_id, str)
    }


@callback
def async_get_all_device_ids(hass: HomeAssistant) -> set[str]:
    """Return all device IDs, known to Home Assistant."""
    device_registry = dr.async_get(hass)
    return {device.id for device in device_registry.devices.values()}


@callback
def async_filter_known_device_ids(
    hass: HomeAssistant,
    *,
    device_ids: set[str],
    known_device_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known device IDs."""
    if known_device_ids is None:
        known_device_ids = async_get_all_device_ids(hass)
    return {
        device_id
        for device_id in device_ids - known_device_ids
        if device_id and isinstance(device_id, str)
    }


@callback
def async_filter_known_entity_ids(
    hass: HomeAssistant,
    entity_ids: Iterable[str],
    known_entity_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known entity IDs.

    This callback version skips template processing. For template support,
    use async_filter_known_entity_ids_with_templates instead.
    """
    if known_entity_ids is None:
        known_entity_ids = async_get_all_entity_ids(hass)

    result = set()
    for entity_id_raw in entity_ids:
        if not isinstance(entity_id_raw, str):
            continue

        # Process any comma-separated entity lists
        for entity_id in split_comma_separated_entity_ids(entity_id_raw):
            if (
                not entity_id.startswith(IGNORED_ENTITY_DOMAINS)
                and entity_id not in known_entity_ids
                and valid_entity_id(entity_id)
            ):
                result.add(entity_id)

    return result


@callback
def async_get_all_floor_ids(hass: HomeAssistant) -> set[str]:
    """Return all floor IDs, known to Home Assistant."""
    floor_registry = fr.async_get(hass)
    return {floor.floor_id for floor in floor_registry.floors.values()}


@callback
def async_filter_known_floor_ids(
    hass: HomeAssistant,
    *,
    floor_ids: set[str],
    known_floor_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known floor IDs."""
    if known_floor_ids is None:
        known_floor_ids = async_get_all_label_ids(hass)
    return {
        floor_id
        for floor_id in floor_ids - known_floor_ids
        if floor_id and isinstance(floor_id, str)
    }


@callback
def async_get_all_label_ids(hass: HomeAssistant) -> set[str]:
    """Return all label IDs, known to Home Assistant."""
    label_registry = lr.async_get(hass)
    return {label.label_id for label in label_registry.labels.values()}


@callback
def async_filter_known_label_ids(
    hass: HomeAssistant,
    *,
    label_ids: set[str],
    known_label_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known label IDs."""
    if known_label_ids is None:
        known_label_ids = async_get_all_label_ids(hass)
    return {
        label_id
        for label_id in label_ids - known_label_ids
        if label_id and isinstance(label_id, str)
    }


@callback
def async_get_all_services(hass: HomeAssistant) -> set[str]:
    """Return all services, known to Home Assistant."""
    return {
        f"{domain}.{service}"
        for domain, services in hass.services.async_services().items()
        for service in services
    }


@callback
def async_filter_known_services(
    hass: HomeAssistant, *, services: set[str], known_services: set[str] | None = None
) -> set[str]:
    """Filter out known services."""
    if known_services is None:
        known_services = async_get_all_services(hass)
    return {
        service.lower()
        for service in services - known_services
        if isinstance(service, str) and service
    }


def is_template_string(value: str) -> bool:
    """Check if a string looks like a Jinja2 template."""
    if not isinstance(value, str):
        return False
    return ("{{" in value and "}}" in value) or ("{%" in value and "%}" in value)


async def async_extract_entities_from_template_string(
    hass: HomeAssistant, template_str: str
) -> set[str]:
    """Extract entity IDs from a template string using regex analysis.

    This function uses regex patterns based on Home Assistant's core validation
    patterns to find entity IDs referenced in template functions.
    """
    if not is_template_string(template_str):
        return set()

    entities = set()

    # Use regex patterns to find entities
    try:
        regex_entities = extract_entities_from_template_regex(hass, template_str)
        entities.update(regex_entities)
    # pylint: disable-next=broad-exception-caught
    except Exception as exc:  # noqa: BLE001 - Keep broad for unexpected regex issues
        LOGGER.debug(
            "Failed to extract entities from template '%s...' using regex.",
            template_str[:50],
            exc_info=exc,  # Pass the exception for logging
        )

    return entities


def extract_entities_from_template_regex(
    hass: HomeAssistant, template_str: str
) -> set[str]:
    """Extract entity IDs from template string using regex patterns.

    This function uses regex patterns based on Home Assistant's core validation
    patterns to find entity IDs referenced in template functions. It's designed
    to complement the RenderInfo analysis by catching entities that might be
    missed by template parsing.
    """
    if not isinstance(template_str, str):
        return set()

    entities = set()
    # Number of capture groups in states.domain.entity pattern
    domain_entity_groups = 2

    for pattern in ENTITY_ID_TEMPLATE_PATTERNS:
        matches = re.findall(pattern, template_str, re.IGNORECASE)
        for match in matches:
            # Handle the states.domain.entity pattern that captures (domain, object_id)
            if isinstance(match, tuple) and len(match) == domain_entity_groups:
                entity_id = f"{match[0]}.{match[1]}"
            else:
                entity_id = match

            # For each entity ID (which might be comma-separated), add all valid ones
            for individual_id in split_comma_separated_entity_ids(entity_id):
                if valid_entity_id(individual_id):
                    entities.add(individual_id)

    # Filter out known services to avoid false positives
    known_services = async_get_all_services(hass)
    return entities - known_services


async def _process_template_object(
    hass: HomeAssistant,
    template: Template,
    known_entity_ids: set[str],
    unknown_entities: set[str],
) -> None:
    """Process a Template object and add unknown entities to the set."""
    template_entities = set()

    # Use regex patterns on the template string
    try:
        if hasattr(template, "template") and template.template:
            regex_entities = extract_entities_from_template_regex(
                hass, template.template
            )
            template_entities.update(regex_entities)
    # pylint: disable-next=broad-exception-caught
    except Exception:  # noqa: BLE001
        LOGGER.debug("Error in regex entity extraction for Template object")

    # Check if any of the template entities are unknown
    for template_entity in template_entities:
        if template_entity not in known_entity_ids:
            unknown_entities.add(template_entity)


async def _process_template_string(
    hass: HomeAssistant,
    template_str: str,
    known_entity_ids: set[str],
    unknown_entities: set[str],
) -> None:
    """Process a template string and add unknown entities to the set."""
    template_entities = await async_extract_entities_from_template_string(
        hass, template_str
    )
    # Check if any of the template entities are unknown
    for template_entity in template_entities:
        # Handle comma-separated entity lists
        for entity_id in split_comma_separated_entity_ids(template_entity):
            if (
                entity_id not in known_entity_ids
                and valid_entity_id(entity_id)
                and not entity_id.startswith(IGNORED_ENTITY_DOMAINS)
            ):
                unknown_entities.add(entity_id)


async def async_filter_known_entity_ids_with_templates(
    hass: HomeAssistant,
    entity_ids: Iterable[str],
    known_entity_ids: set[str] | None = None,
) -> set[str]:
    """Async version that can process templates to extract entity dependencies.

    This function processes both regular entity IDs and template strings,
    extracting entity dependencies from templates using RenderInfo.
    """
    if known_entity_ids is None:
        known_entity_ids = async_get_all_entity_ids(hass)

    unknown_entities = set()

    for entity_id_raw in entity_ids:
        # Handle Template objects
        if isinstance(entity_id_raw, Template):
            await _process_template_object(
                hass, entity_id_raw, known_entity_ids, unknown_entities
            )
            continue

        if not isinstance(entity_id_raw, str):
            continue

        # Check if this looks like a template string
        if is_template_string(entity_id_raw):
            await _process_template_string(
                hass, entity_id_raw, known_entity_ids, unknown_entities
            )
        else:
            # Process as regular entity ID(s), handling comma-separated lists
            for entity_id in split_comma_separated_entity_ids(entity_id_raw):
                if (
                    not entity_id.startswith(IGNORED_ENTITY_DOMAINS)
                    and entity_id not in known_entity_ids
                    and valid_entity_id(entity_id)
                ):
                    # Process as regular entity ID
                    unknown_entities.add(entity_id)

    return unknown_entities


def split_comma_separated_entity_ids(entity_id: str) -> list[str]:
    """Split comma-separated entity IDs into a list of individual entity IDs.

    Handles both comma-separated entity IDs like "light.living_room,light.kitchen"
    and single entity IDs. Returns a list containing all individual entity IDs.
    """
    if not entity_id or not isinstance(entity_id, str):
        return []

    # Check if the string contains commas
    if "," in entity_id:
        # Split by comma and strip whitespace
        items = [item.strip() for item in entity_id.split(",") if item.strip()]
        if len(items) > 1:
            LOGGER.debug(
                "Split comma-separated entity IDs: %s into %s", entity_id, items
            )
        return items

    # Return the original entity ID in a list if it's not comma-separated
    return [entity_id]


def extract_template_strings_from_config(
    config: Any, strings: list[str] | None = None
) -> list[str]:
    """Recursively extract template strings from configuration data."""
    if strings is None:
        strings = []

    if isinstance(config, str):
        if is_template_string(config):  # Uses the util's is_template_string
            strings.append(config)
    elif isinstance(config, dict):
        for value in config.values():
            extract_template_strings_from_config(value, strings)
    elif isinstance(config, (list, tuple)):
        for item in config:
            extract_template_strings_from_config(item, strings)
    return strings


async def async_extract_entities_from_config(
    hass: HomeAssistant, config: Any
) -> set[str]:
    """Extract entity IDs referenced in templates within a configuration structure."""
    entities = set()
    if not config:
        return entities

    template_strings = extract_template_strings_from_config(config)
    for template_str in template_strings:
        try:
            # async_extract_entities_from_template_string already handles
            # TemplateError and other exceptions internally, logging them.
            referenced_entities = await async_extract_entities_from_template_string(
                hass, template_str
            )
            entities.update(referenced_entities)
        # pylint: disable-next=broad-exception-caught
        except Exception as exc:  # noqa: BLE001 - Keep broad for unexpected issues
            # This catch is a safeguard; internal function should handle most.
            LOGGER.debug(
                "Unexpected error extracting entities from template string "
                "'%s...' in config: %s",
                template_str[:50],
                exc,  # Pass the exception for logging
            )
    return entities


@callback
def async_find_services_in_sequence(  # noqa: C901
    sequence: Sequence[dict[str, Any]],
) -> set[str]:
    """Find all services called in a sequence."""
    called_services: set[str] = set()
    for step in sequence:
        action = cv.determine_script_action(step)

        if (
            action == cv.SCRIPT_ACTION_CALL_SERVICE
            and CONF_SERVICE in step
            and step.get(CONF_ENABLED, True)
        ):
            called_services.add(step[CONF_SERVICE])

        if (
            action == cv.SCRIPT_ACTION_CALL_SERVICE
            and "action" in step
            and step.get(CONF_ENABLED, True)
        ):
            called_services.add(step["action"])

        if action == cv.SCRIPT_ACTION_CHOOSE:
            for choice in step[CONF_CHOOSE]:
                called_services |= async_find_services_in_sequence(
                    choice[CONF_SEQUENCE]
                )
            if nested_sequence := step.get(CONF_DEFAULT):
                called_services |= async_find_services_in_sequence(nested_sequence)

        if action == cv.SCRIPT_ACTION_IF:
            called_services |= async_find_services_in_sequence(step[CONF_THEN])
            if nested_sequence := step.get(CONF_ELSE):
                called_services |= async_find_services_in_sequence(nested_sequence)

        if action == cv.SCRIPT_ACTION_PARALLEL:
            for nested_sequence in step[CONF_PARALLEL]:
                called_services |= async_find_services_in_sequence(
                    nested_sequence[CONF_SEQUENCE]
                )

        if action == cv.SCRIPT_ACTION_REPEAT:
            called_services |= async_find_services_in_sequence(
                step[CONF_REPEAT][CONF_SEQUENCE]
            )

    return called_services
