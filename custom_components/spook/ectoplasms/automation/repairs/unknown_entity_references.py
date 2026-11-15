"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import automation
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....action_extraction import (
    extract_entities_from_action_config,
    extract_entities_from_value,
    unknown_entities_named,
)
from ....entity_filtering import async_get_all_entity_ids, async_get_all_services
from ....reference_extraction import (
    VALUE_KEYS,
    event_payload_keys_to_leave_alone,
    extract_platform_keys_from_config,
    names_given_to_templates,
    threshold_entities,
    without_never_rendered,
)
from ....template_extraction import _extract_entities_from_config
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant, Service

    from ....repairs import InspectedEntity


def extract_template_entities_from_config(
    raw_config: Any,
    known_services: set[str],
) -> set[str]:
    """Extract the entities the templates in a raw configuration name.

    Every template string in it, read the way
    `template_extraction._extract_entities_from_config` reads them.
    """
    if not raw_config:
        return set()

    # A description, a name or a field example is shown, never rendered: an
    # entity in an example template there is not one the automation uses.
    return _extract_entities_from_config(
        without_never_rendered(raw_config),
        known_services,
        names_given_to_templates(raw_config),
    )


def _extract_entities_from_automation_config(
    config: dict[str, Any],
    known_services: set[str],
    shadowed: frozenset[str] | None = None,
) -> set[str]:
    """Extract entity IDs from automation configuration.

    The synchronous core of `extract_entities_from_automation_config`,
    with the services already known: pure computation over plain data, so
    it can run in an executor, away from the event loop.
    """
    entities = set()

    if not isinstance(config, dict):
        return entities

    if shadowed is None:
        shadowed = names_given_to_templates(config)

    # Extract entities from trigger config
    for key in ("trigger", "triggers"):
        if key in config:
            entities.update(
                _extract_entities_from_trigger_config(
                    config[key], known_services, shadowed=shadowed
                )
            )

    # Extract entities from condition config
    for key in ("condition", "conditions"):
        if key in config:
            entities.update(
                _extract_entities_from_condition_config(
                    config[key], known_services, shadowed=shadowed
                )
            )

    # Extract entities from action config
    for key in ("action", "actions"):
        if key in config:
            entities.update(
                extract_entities_from_action_config(
                    config[key],
                    known_services=known_services,
                    shadowed=shadowed,
                )
            )

    return entities


async def extract_entities_from_automation_config(
    hass: HomeAssistant,
    config: dict[str, Any],
    known_services: set[str] | None = None,
    shadowed: frozenset[str] | None = None,
) -> set[str]:
    """Extract entity IDs from automation configuration.

    ``known_services`` is built once per inspection and handed down, because
    building it flattens every service Home Assistant has and the walk below
    passes a lot of template strings. See
    `action_extraction.async_extract_entities_from_action_config`.

    The names the automation gives its templates, like a variable called
    `states`, are taken from all of it here, before walking its parts,
    unless ``shadowed`` already holds them.
    """
    if known_services is None:
        known_services = async_get_all_services(hass)
    return _extract_entities_from_automation_config(config, known_services, shadowed)


def _entities_from_reference_fields(
    config: dict[str, Any],
    known_services: set[str],
    *,
    in_values: bool = False,
    shadowed: frozenset[str] = frozenset(),
) -> set[str]:
    """Extract entities from the config keys that name a reference.

    ``zone`` is in here because a zone trigger and a zone condition both name
    one, and it is read exactly like the others. So is the entity a trigger
    or condition takes as its threshold, unless the dictionary sits below a
    key that holds values: event data that only looks like one is still event
    data.
    """
    entities = set() if in_values else threshold_entities(config)
    for key in ("entity_id", "device_id", "zone"):
        if key in config:
            entities.update(
                extract_entities_from_value(
                    config[key], known_services=known_services, shadowed=shadowed
                )
            )
    return entities


def _extract_entities_from_trigger_config(
    config: dict[str, Any] | list,
    known_services: set[str],
    *,
    _in_values: bool = False,
    shadowed: frozenset[str] = frozenset(),
) -> set[str]:
    """Extract entity IDs from trigger configuration.

    The synchronous core of `extract_entities_from_trigger_config`, with
    the services already known: pure computation over plain data, so it
    can run in an executor, away from the event loop.
    """
    entities = set()

    if not config:
        return entities

    if isinstance(config, list):
        for item in config:
            entities.update(
                _extract_entities_from_trigger_config(
                    item,
                    known_services,
                    _in_values=_in_values,
                    shadowed=shadowed,
                )
            )
        return entities

    if not isinstance(config, dict):
        return entities

    entities.update(
        _entities_from_reference_fields(
            config, known_services, in_values=_in_values, shadowed=shadowed
        )
    )

    payload_keys = event_payload_keys_to_leave_alone(config)

    # Extract from nested configs
    for key, value in config.items():
        if key in payload_keys:
            continue

        if isinstance(value, (dict, list)):
            entities.update(
                _extract_entities_from_trigger_config(
                    value,
                    known_services,
                    _in_values=_in_values or key in VALUE_KEYS,
                    shadowed=shadowed,
                )
            )

    return entities


async def extract_entities_from_trigger_config(
    hass: HomeAssistant,
    config: dict[str, Any] | list,
    known_services: set[str] | None = None,
    *,
    _in_values: bool = False,
    shadowed: frozenset[str] = frozenset(),
) -> set[str]:
    """Extract entity IDs from trigger configuration."""
    if not config:
        return set()

    if known_services is None:
        known_services = async_get_all_services(hass)

    return _extract_entities_from_trigger_config(
        config, known_services, _in_values=_in_values, shadowed=shadowed
    )


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


def _extract_entities_from_condition_config(
    config: dict[str, Any] | list,
    known_services: set[str],
    *,
    _in_values: bool = False,
    shadowed: frozenset[str] = frozenset(),
) -> set[str]:
    """Extract entity IDs from condition configuration.

    The synchronous core of `extract_entities_from_condition_config`, with
    the services already known: pure computation over plain data, so it
    can run in an executor, away from the event loop.
    """
    entities = set()

    if not config:
        return entities

    if isinstance(config, list):
        for item in config:
            entities.update(
                _extract_entities_from_condition_config(
                    item,
                    known_services,
                    _in_values=_in_values,
                    shadowed=shadowed,
                )
            )
        return entities

    if not isinstance(config, dict):
        return entities

    entities.update(
        _entities_from_reference_fields(
            config, known_services, in_values=_in_values, shadowed=shadowed
        )
    )

    # Extract from nested configs
    for key, value in config.items():
        if isinstance(value, (dict, list)):
            entities.update(
                _extract_entities_from_condition_config(
                    value,
                    known_services,
                    _in_values=_in_values or key in VALUE_KEYS,
                    shadowed=shadowed,
                )
            )

    return entities


async def extract_entities_from_condition_config(
    hass: HomeAssistant,
    config: dict[str, Any] | list,
    known_services: set[str] | None = None,
    *,
    _in_values: bool = False,
    shadowed: frozenset[str] = frozenset(),
) -> set[str]:
    """Extract entity IDs from condition configuration."""
    if not config:
        return set()

    if known_services is None:
        known_services = async_get_all_services(hass)

    return _extract_entities_from_condition_config(
        config, known_services, _in_values=_in_values, shadowed=shadowed
    )


class SpookRepair(AbstractSpookAutomationReferencesRepair):
    """Spook repair tries to find unknown referenced entity in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True
    inspect_on_entity_added_or_removed = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "entities"
    references_are_entities = True
    edit_url_pattern = "/config/automation/edit/{unique_id}"
    core_reference_kind = "entities"

    _known_entity_ids: set[str]
    _known_services: set[str]
    _services: Mapping[str, Mapping[str, Service]]

    async def _async_setup_inspection(self) -> None:
        """Cache what every automation in this cycle needs looked up.

        The service set is in here for the same reason as the entity ids:
        building it flattens every service Home Assistant has, and it is the
        same answer for every automation in one pass.
        """
        self._known_entity_ids = async_get_all_entity_ids(
            self.hass, include_all_none=True
        )
        self._known_services = async_get_all_services(self.hass)
        # The registry itself, for telling what an action hands over as an
        # `entity_id` that is no entity ID: read on the event loop, so the
        # computation in the executor never has to reach back for it.
        self._services = self.hass.services.async_services()

    def _named_in(self, config: dict[str, Any], shadowed: frozenset[str]) -> set[str]:
        """Return the entities a configuration names, the way this repair reads it.

        The same reading the report is built from, structure and templates
        alike, so comparing it with and without the disabled steps leaves out
        exactly what only those name. ``shadowed`` comes from the whole
        configuration, as `config` can be one without its disabled steps.
        """
        named = _extract_entities_from_automation_config(
            config, self._known_services, shadowed
        )
        named |= _extract_entities_from_config(
            without_never_rendered(config),
            self._known_services,
            shadowed,
        )
        return named

    def _compute_unknown_references(self, entity: InspectedEntity) -> set[str]:
        """Return unknown entity IDs referenced by ``entity`` (incl. templates)."""
        all_entities = entity.core_references()

        # Also extract entities directly from raw configuration if available
        if entity.raw_config:
            all_entities.update(
                _extract_entities_from_automation_config(
                    entity.raw_config, self._known_services
                )
            )

        # Extract entities from the templates within the configuration
        all_entities.update(
            extract_template_entities_from_config(
                entity.raw_config, self._known_services
            )
        )

        raw_config = entity.raw_config
        if raw_config:
            # The kinds of trigger and event this automation listens for look
            # like entity IDs, `sun.dusk` and `timer.finished` for two, and a
            # template comparing `trigger.platform` or the event type with
            # one names no entity at all.
            all_entities.difference_update(
                extract_platform_keys_from_config(raw_config).trigger_keys
            )
            for key in ("trigger", "triggers"):
                all_entities.difference_update(
                    extract_event_types_from_trigger_config(raw_config.get(key))
                )

        return unknown_entities_named(
            all_entities,
            raw_config,
            named_in=self._named_in,
            known_entity_ids=self._known_entity_ids,
            known_services=self._known_services,
            services=self._services,
        )
