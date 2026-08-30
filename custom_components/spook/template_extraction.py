"""Spook - Your homie. Template entity reference extraction helpers."""

from __future__ import annotations

from functools import lru_cache
import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import Platform
from homeassistant.core import valid_entity_id
from homeassistant.helpers.template import Template

from .const import LOGGER
from .entity_filtering import (
    IGNORED_ENTITY_DOMAINS,
    NEVER_AN_ENTITY,
    async_drop_existing_action_names,
    async_get_all_entity_ids,
    async_get_all_services,
    split_comma_separated_entity_ids,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant

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
_STATES_DOMAIN_ENTITY_GROUPS = 2


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


COMPILED_ENTITY_ID_TEMPLATE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE) for pattern in ENTITY_ID_TEMPLATE_PATTERNS
)


JINJA_COMMENT_PATTERN = re.compile(r"\{#.*?#\}", re.DOTALL)

# The ``device_entities`` template function takes a device registry ID
# directly (no name or entity resolution), so a quoted literal is
# unambiguously a device reference.
_DEVICE_ENTITIES_PATTERN = re.compile(
    r"device_entities\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def is_template_string(value: str) -> bool:
    """Check if a string looks like a Jinja2 template."""
    if not isinstance(value, str):
        return False
    return ("{{" in value and "}}" in value) or ("{%" in value and "%}" in value)


async def async_extract_entities_from_template_string(
    hass: HomeAssistant,
    template_str: str,
    known_services: set[str] | None = None,
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
        regex_entities = extract_entities_from_template_regex(
            hass, template_str, known_services
        )
        entities.update(regex_entities)
    # pylint: disable-next=broad-exception-caught
    except Exception as exc:  # noqa: BLE001 - Keep broad for unexpected regex issues
        LOGGER.debug(
            "Failed to extract entities from template '%s...' using regex.",
            template_str[:50],
            exc_info=exc,  # Pass the exception for logging
        )

    return entities


def _strip_jinja_comments(template_str: str) -> str:
    """Remove Jinja comments from a template string."""
    if "{#" not in template_str:
        return template_str
    return JINJA_COMMENT_PATTERN.sub("", template_str)


def _is_concatenated_template_match(template_str: str, match: re.Match[str]) -> bool:
    """Return if a quoted entity ID literal is part of a concatenated string."""
    groups = match.groups()
    if len(groups) == _STATES_DOMAIN_ENTITY_GROUPS:
        return False

    entity_start, entity_end = match.span(1)
    before_entity = template_str[:entity_start].rstrip()
    after_entity = template_str[entity_end:].lstrip()

    if not (before_entity.endswith(("'", '"')) and after_entity.startswith(("'", '"'))):
        return False

    before_literal = before_entity[:-1].rstrip()
    after_literal = after_entity[1:].lstrip()
    return before_literal.endswith("~") or after_literal.startswith("~")


def _is_jinja_import_match(template_str: str, match: re.Match[str]) -> bool:
    """Return if a quoted entity-like literal is a Jinja import filename."""
    groups = match.groups()
    if len(groups) == _STATES_DOMAIN_ENTITY_GROUPS:
        return False

    entity_start, entity_end = match.span(1)
    block_start = template_str.rfind("{%", 0, entity_start)
    expression_start = template_str.rfind("{{", 0, entity_start)
    if block_start == -1 or expression_start > block_start:
        return False

    block_end = template_str.find("%}", entity_end)
    expression_end = template_str.find("}}", entity_end)
    if block_end == -1 or (expression_end != -1 and expression_end < block_end):
        return False

    block = template_str[block_start : block_end + 2]
    return bool(
        re.match(
            r"\{%-?\s*(?:from\s+['\"][^'\"]+['\"]\s+import|import\s+['\"][^'\"]+['\"]\s+as)",
            block,
        )
    )


def _is_string_method_argument_match(template_str: str, match: re.Match[str]) -> bool:
    """Return if an entity-like literal is used as a string method argument."""
    groups = match.groups()
    if len(groups) == _STATES_DOMAIN_ENTITY_GROUPS:
        return False

    entity_start = match.span(1)[0]
    before_entity = template_str[:entity_start].rstrip()
    if not before_entity.endswith(("'", '"')):
        return False

    before_literal = before_entity[:-1].rstrip()
    for method in (".startswith", ".endswith"):
        if method not in before_literal:
            continue

        after_method = before_literal.rsplit(method, maxsplit=1)[1].lstrip()
        if not after_method.startswith("("):
            continue

        between_call_and_argument = after_method[1:].strip()
        if not between_call_and_argument or set(between_call_and_argument) == {"("}:
            return True

    return False


def _entity_id_from_template_match(match: re.Match[str]) -> str:
    """Return the entity ID captured by a template regex match."""
    groups = match.groups()

    # Handle the states.domain.entity pattern that captures (domain, object_id)
    if len(groups) == _STATES_DOMAIN_ENTITY_GROUPS:
        return f"{groups[0]}.{groups[1]}"

    return groups[0]


@lru_cache(maxsize=1024)
def _extract_entity_candidates_from_template(template_str: str) -> frozenset[str]:
    """Extract entity ID candidates from a template string.

    Pure in the template string, so results are cached: repairs re-inspect
    the same unchanged templates over and over.
    """
    template_without_comments = _strip_jinja_comments(template_str)

    entities = set()

    for pattern in COMPILED_ENTITY_ID_TEMPLATE_PATTERNS:
        for match in pattern.finditer(template_without_comments):
            if (
                _is_concatenated_template_match(template_without_comments, match)
                or _is_jinja_import_match(template_without_comments, match)
                or _is_string_method_argument_match(template_without_comments, match)
            ):
                continue

            entity_id = _entity_id_from_template_match(match)

            # For each entity ID (which might be comma-separated), add all valid ones
            for individual_id in split_comma_separated_entity_ids(entity_id):
                if individual_id in NEVER_AN_ENTITY:
                    continue
                if valid_entity_id(individual_id):
                    entities.add(individual_id)

    return frozenset(entities)


def extract_entities_from_template_regex(
    hass: HomeAssistant,
    template_str: str,
    known_services: set[str] | None = None,
) -> set[str]:
    """Extract entity IDs from template string using regex patterns.

    This function uses regex patterns based on Home Assistant's core validation
    patterns to find entity IDs referenced in template functions. It's designed
    to complement the RenderInfo analysis by catching entities that might be
    missed by template parsing.
    """
    if not isinstance(template_str, str):
        return set()

    entities = set(_extract_entity_candidates_from_template(template_str))

    # Filter out known services to avoid false positives
    if known_services is None:
        known_services = async_get_all_services(hass)
    return entities - known_services


async def _process_template_object(
    hass: HomeAssistant,
    template: Template,
    known_entity_ids: set[str],
    known_services: set[str],
    unknown_entities: set[str],
) -> None:
    """Process a Template object and add unknown entities to the set."""
    template_entities = set()

    # Use regex patterns on the template string
    try:
        if hasattr(template, "template") and template.template:
            regex_entities = extract_entities_from_template_regex(
                hass, template.template, known_services
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
    known_services: set[str],
    unknown_entities: set[str],
) -> None:
    """Process a template string and add unknown entities to the set."""
    template_entities = await async_extract_entities_from_template_string(
        hass, template_str, known_services
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
    extracting entity dependencies from templates using RenderInfo. Names that
    belong to an existing action are dropped, since those are not entities.
    """
    if known_entity_ids is None:
        known_entity_ids = async_get_all_entity_ids(hass)
    known_services: set[str] | None = None

    unknown_entities = set()

    for entity_id_raw in entity_ids:
        # Handle Template objects
        if isinstance(entity_id_raw, Template):
            if known_services is None:
                known_services = async_get_all_services(hass)
            await _process_template_object(
                hass, entity_id_raw, known_entity_ids, known_services, unknown_entities
            )
            continue

        if not isinstance(entity_id_raw, str):
            continue

        # Check if this looks like a template string
        if is_template_string(entity_id_raw):
            if known_services is None:
                known_services = async_get_all_services(hass)
            await _process_template_string(
                hass, entity_id_raw, known_entity_ids, known_services, unknown_entities
            )
        else:
            # Process as regular entity ID(s), handling comma-separated lists
            for entity_id in split_comma_separated_entity_ids(entity_id_raw):
                if (
                    entity_id not in NEVER_AN_ENTITY
                    and not entity_id.startswith(IGNORED_ENTITY_DOMAINS)
                    and entity_id not in known_entity_ids
                    and valid_entity_id(entity_id)
                ):
                    # Process as regular entity ID
                    unknown_entities.add(entity_id)

    return async_drop_existing_action_names(hass, unknown_entities)


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
    hass: HomeAssistant,
    config: Any,
    known_services: set[str] | None = None,
) -> set[str]:
    """Extract entity IDs referenced in templates within a configuration structure.

    ``known_services`` is what tells an action name apart from an entity id.
    Building it flattens every service Home Assistant has, so a caller walking
    one configuration after another should build it once and pass it in.
    """
    entities = set()
    if not config:
        return entities

    template_strings = extract_template_strings_from_config(config)
    if known_services is None:
        known_services = async_get_all_services(hass) if template_strings else set()
    extracted_templates: dict[str, set[str]] = {}
    for template_str in template_strings:
        try:
            # async_extract_entities_from_template_string already handles
            # TemplateError and other exceptions internally, logging them.
            if template_str not in extracted_templates:
                extracted_templates[
                    template_str
                ] = await async_extract_entities_from_template_string(
                    hass, template_str, known_services
                )
            referenced_entities = extracted_templates[template_str]
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


@lru_cache(maxsize=1024)
def _extract_device_ids_from_template(template_str: str) -> frozenset[str]:
    """Extract device IDs referenced via ``device_entities`` in a template."""
    template_without_comments = _strip_jinja_comments(template_str)
    return frozenset(_DEVICE_ENTITIES_PATTERN.findall(template_without_comments))


def extract_device_ids_from_config(config: Any) -> set[str]:
    """Extract device IDs referenced via ``device_entities`` in templates."""
    device_ids: set[str] = set()
    for template_str in extract_template_strings_from_config(config):
        device_ids.update(_extract_device_ids_from_template(template_str))
    return device_ids
