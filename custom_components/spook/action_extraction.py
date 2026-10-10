"""Spook - Your homie. Action configuration entity reference extraction helpers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID, CONF_ENABLED
from homeassistant.helpers import config_validation as cv

from .const import LOGGER
from .entity_filtering import (
    NEVER_AN_ENTITY_PREFIXES,
    async_get_all_services,
    is_not_an_entity_id,
    split_comma_separated_entity_ids,
)
from .reference_extraction import (
    VALUE_KEYS,
    event_payload_keys_to_leave_alone,
    names_given_to_templates,
    numeric_state_threshold_entities,
    without_disabled_steps,
    without_never_rendered,
)
from .template_extraction import (
    ENTITY_ID_PATTERN,
    async_extract_entities_from_template_string,
    extract_not_entity_ids_from_template,
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
    _in_values: bool = False,
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
                    _in_values=_in_values,
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

    # A condition or a trigger waited for in a step can compare against an
    # entity. Below a key that holds values, like action data, event data or
    # variables, nothing is either, whatever its shape.
    if not _in_values:
        entities.update(numeric_state_threshold_entities(config))

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
            _in_values=_in_values,
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

    if service == "script.turn_on":
        entities.update(
            await _extract_entities_from_script_variables(hass, config, known_services)
        )

    return entities


async def _extract_entities_from_script_variables(
    hass: HomeAssistant,
    config: dict[str, Any],
    known_services: set[str],
) -> set[str]:
    """Extract entities from the variables script.turn_on hands a script.

    script.turn_on hands the script its fields under `variables`, where
    calling the script by name takes them as the data itself. Either way
    they become the same script variables, so they are read the same way.
    Home Assistant merges the old `data_template` into the data, so the
    variables can sit in either.
    """
    entities = set()
    for data_key in _ACTION_DATA_KEYS:
        data_value = config.get(data_key)
        if not isinstance(data_value, dict):
            continue

        variables = data_value.get("variables")
        if not isinstance(variables, dict):
            continue

        for value in variables.values():
            entities.update(
                await async_extract_entities_from_value(
                    hass, value, known_services=known_services
                )
            )

    return entities


# Where an action keeps the data it hands over. `data_template` is the old
# name, which Home Assistant still takes and merges into the data.
_ACTION_DATA_KEYS = frozenset({"data", "data_template"})


async def _extract_entities_from_nested_configs(
    hass: HomeAssistant,
    config: dict[str, Any],
    known_services: set[str],
    *,
    include_disabled: bool = True,
    in_payload: bool = False,
    _in_values: bool = False,
    _service: str | None = None,
) -> set[str]:
    """Extract entities from nested configurations.

    The payload of somebody's own event waited for in a step is left alone:
    it is whatever the sender puts there, not something this one needs.
    Inside action data nothing is a trigger, whatever its shape.
    """
    entities = set()
    payload_keys = (
        frozenset() if in_payload else event_payload_keys_to_leave_alone(config)
    )
    for key, value in config.items():
        if key in payload_keys:
            continue
        if isinstance(value, (dict, list)):
            entities.update(
                await async_extract_entities_from_action_config(
                    hass,
                    value,
                    include_disabled=include_disabled,
                    known_services=known_services,
                    _in_payload=in_payload or key in _ACTION_DATA_KEYS,
                    _is_payload=key in _ACTION_DATA_KEYS,
                    _in_values=_in_values or key in VALUE_KEYS,
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


# How Home Assistant's own actions check an `entity_id` handed to them. An
# entity action, made with `make_entity_service_schema`, checks it with
# `comp_entity_ids`. A few others, like `homeassistant.turn_on`, ask for one
# of these in a schema of their own.
_ENTITY_ID_VALIDATORS = (cv.entity_id, cv.entity_ids, cv.comp_entity_ids)

# The order Home Assistant merges the data in: `data_template` goes last, so
# an `entity_id` in there is the one the action gets.
_DATA_KEYS_LAST_FIRST = ("data_template", "data")


def _action_checks_entity_id(hass: HomeAssistant, action: str) -> bool:
    """Return whether this action refuses an `entity_id` that is no entity ID.

    Home Assistant only checks action data when the action runs, against
    the action's own schema. One that has no schema, or keeps `entity_id`
    for something of its own, like a script handed it as a field, takes
    anything. So only an action that exists right now, and checks it.
    """
    domain, _, service = action.lower().partition(".")
    registered = hass.services.async_services_for_domain(domain).get(service)
    if registered is None or (schema := registered.schema) is None:
        return False

    if cv.is_entity_service_schema(schema):
        return True

    fields = getattr(schema, "schema", None)
    return isinstance(fields, dict) and any(
        fields.get(ATTR_ENTITY_ID) is validator for validator in _ENTITY_ID_VALIDATORS
    )


def _data_entity_id(config: dict[str, Any]) -> Any:
    """Return the `entity_id` an action takes from its data, if it gets that one.

    A target and an `entity_id` on the step go over the data, as does data
    rendered from a template: what that holds is only known when it runs.
    """
    target = config.get("target")
    if ATTR_ENTITY_ID in config or (
        target is not None
        and (not isinstance(target, dict) or ATTR_ENTITY_ID in target)
    ):
        return None

    for key in _DATA_KEYS_LAST_FIRST:
        data = config.get(key)
        if isinstance(data, str):
            return None
        if isinstance(data, dict) and ATTR_ENTITY_ID in data:
            return data[ATTR_ENTITY_ID]
    return None


def _not_entity_ids_in_data(hass: HomeAssistant, config: dict[str, Any]) -> set[str]:
    """Return what an action hands over as `entity_id` data that is no entity ID.

    The old way of writing a target. Home Assistant takes text with commas
    as a list, and a template in there is whatever it renders to.
    """
    action = _get_action_service(config)
    if action is None or not _action_checks_entity_id(hass, action):
        return set()

    value = _data_entity_id(config)
    values = value if isinstance(value, list) else [value]
    return {
        entity_id
        for item in values
        if not is_template_string(item)
        # Anything but text, like a number, splits into nothing.
        for entity_id in split_comma_separated_entity_ids(item)
        if is_not_an_entity_id(entity_id)
    }


def _collect_not_entity_ids(
    hass: HomeAssistant,
    config: Any,
    shadowed: frozenset[str],
    found: set[str],
    *,
    in_values: bool = False,
) -> None:
    """Collect what a part of a configuration names that is no entity ID."""
    if isinstance(config, str):
        # Asked first, so plain text does not push templates out of the cache.
        if is_template_string(config):
            found.update(extract_not_entity_ids_from_template(config, shadowed))
        return

    if isinstance(config, list):
        for item in config:
            _collect_not_entity_ids(hass, item, shadowed, found, in_values=in_values)
        return

    if not isinstance(config, dict):
        return

    # Below a key that holds values, nothing is an action, whatever its shape.
    if not in_values:
        found.update(_not_entity_ids_in_data(hass, config))

    # Somebody's own event is whatever the sender puts there.
    payload_keys = event_payload_keys_to_leave_alone(config)
    for key, value in config.items():
        if key in payload_keys:
            continue
        _collect_not_entity_ids(
            hass, value, shadowed, found, in_values=in_values or key in VALUE_KEYS
        )


def extract_not_entity_ids_from_config(hass: HomeAssistant, config: Any) -> set[str]:
    """Return what an automation or script names as an entity that is no entity ID.

    Two places only, both of which Home Assistant first looks at while
    running. The `entity_id` an action takes as data, which the action
    refuses then. And the literal handed to a template lookup like
    `states()`, which finds nothing. A trigger, a condition and a target
    are checked by Home Assistant when it loads them, and it says so itself.

    Disabled steps do nothing, and text that is only shown is never
    rendered, so neither is read. A name the configuration gives its
    templates hides a lookup called by that name.
    """
    found: set[str] = set()
    _collect_not_entity_ids(
        hass,
        without_never_rendered(without_disabled_steps(config)),
        names_given_to_templates(config),
        found,
    )
    return found
