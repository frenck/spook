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
    from collections.abc import Mapping

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
    _is_payload: bool = False,
    _service: str | None = None,
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

    A service named on the action decides which of its data fields are plain
    text, and whether a ``target`` in there belongs to notify. The value of
    ``data`` is payload, not an action: a ``service`` key there is a field,
    so the service resolved further out still judges the fields beside it.
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
                    _is_payload=_is_payload,
                    _service=_service,
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

    # The action's own name wins. A `service` key on the `data` payload is a
    # field, not a new action, so the name from further out still applies.
    service = _get_action_service(config, is_payload=_is_payload) or _service

    # Extract entity IDs from direct fields
    entities.update(
        await _extract_entities_from_action_fields(hass, config, known_services)
    )

    # Extract entities from target configuration
    entities.update(await _extract_entities_from_target(hass, config, known_services))

    # Extract entities from service data
    entities.update(
        await _extract_entities_from_service_data(hass, config, known_services, service)
    )

    # Extract from nested configs (like if/then/else, repeat, etc.)
    entities.update(
        await _extract_entities_from_nested_configs(
            hass,
            config,
            known_services,
            include_disabled=include_disabled,
            in_payload=_in_payload,
            _service=service,
        )
    )

    return entities


async def async_extract_entities_from_helper_actions(
    hass: HomeAssistant,
    options: Mapping[str, Any],
    *,
    include_disabled: bool = True,
    known_services: set[str],
) -> set[str]:
    """Extract entity IDs from the actions in a helper's options.

    Template helpers can run action sequences: a button's press, a switch's
    turn_on/turn_off, a cover's open/close, an alarm's arm/disarm and so on.
    Those reference entities through structured config (target, entity_id,
    service data) rather than through Jinja, so reading the templates alone
    does not see them.
    """
    entities: set[str] = set()
    for option in options.values():
        # Only structured options can hold an action; a plain string option
        # walks straight back out of the extractor.
        if not isinstance(option, (dict, list)):
            continue

        entities |= await async_extract_entities_from_action_config(
            hass,
            option,
            include_disabled=include_disabled,
            known_services=known_services,
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


def _get_action_service(
    config: dict[str, Any], *, is_payload: bool = False
) -> str | None:
    """Return the action's service name, ignoring a payload ``service`` field."""
    if is_payload:
        return None
    service = config.get("service", config.get("action"))
    return service if isinstance(service, str) else None


def _should_skip_service_data_value(
    service: str | None,
    key: str,
) -> bool:
    """Return if a service data value should not be scanned for entity IDs."""
    return service is not None and service.startswith("notify.") and key == "target"


# Action data fields that are words for a person to read, or an identifier
# the service keeps as text: a notification, a spoken announcement, the title
# above either, the tag a phone uses to replace an earlier notification, the
# logger name a log line is filed under. A template in one can name an
# entity, and that is a reference like any other. Plain text that happens to
# look like an entity ID is still just text, and it goes out saying exactly
# that.
#
# Which fields those are depends on the integration. Notify treats
# `message`, `title` and `tag` as text; assist_satellite,
# persistent_notification and tts treat `message` and `title` that way;
# system_log treats `logger` and `message` that way. Anything else, a script
# field or a custom action without a schema, is free to call one of its
# fields `message` or `tag` and put an entity ID in it.
_FREE_TEXT_FIELDS: dict[str, frozenset[str]] = {
    "assist_satellite": frozenset({"message", "title"}),
    "notify": frozenset({"message", "tag", "title"}),
    "persistent_notification": frozenset({"message", "title"}),
    "system_log": frozenset({"logger", "message"}),
    "tts": frozenset({"message", "title"}),
}


def _is_plain_text(service: str | None, key: str, value: Any) -> bool:
    """Return whether this data value is plain text, not something to resolve."""
    return (
        service is not None
        and key in _FREE_TEXT_FIELDS.get(service.split(".", 1)[0], ())
        and isinstance(value, str)
        and not is_template_string(value)
    )


async def _extract_entities_from_service_data(
    hass: HomeAssistant,
    config: dict[str, Any],
    known_services: set[str],
    service: str | None,
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
            # data field is a dictionary, process all its values
            for key, value in data_value.items():
                if _should_skip_service_data_value(service, key):
                    continue
                if _is_plain_text(service, key, value):
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
    _service: str | None = None,
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
                    _is_payload=key == "data",
                    _service=_service,
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
        elif not value.startswith(NEVER_AN_ENTITY_PREFIXES) and _ENTITY_ID_RE.match(
            value
        ):
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
