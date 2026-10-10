"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import automation
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....action_extraction import (
    async_extract_entities_from_action_config,
    async_extract_entities_from_value,
    extract_not_entity_ids_from_config,
)
from ....entity_filtering import async_get_all_entity_ids, async_get_all_services
from ....reference_extraction import (
    VALUE_KEYS,
    core_references,
    event_payload_keys_to_leave_alone,
    harmless_entity_mentions,
    mentioned_only_in_disabled_steps,
    numeric_state_threshold_entities,
    without_disabled_steps,
    without_never_rendered,
)
from ....template_extraction import (
    async_extract_entities_from_config,
    async_filter_known_entity_ids_with_templates,
)
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def extract_template_entities_from_automation_entity(
    hass: HomeAssistant,
    entity: Any,
    known_services: set[str] | None = None,
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

    # A description, a name or a field example is shown, never rendered: an
    # entity in an example template there is not one the automation uses.
    return await async_extract_entities_from_config(
        hass, without_never_rendered(config), known_services
    )


async def extract_entities_from_automation_config(
    hass: HomeAssistant,
    config: dict[str, Any],
    known_services: set[str] | None = None,
) -> set[str]:
    """Extract entity IDs from automation configuration.

    ``known_services`` is built once per inspection and handed down, because
    building it flattens every service Home Assistant has and the walk below
    passes a lot of template strings. See
    `action_extraction.async_extract_entities_from_action_config`.
    """
    entities = set()

    if not isinstance(config, dict):
        return entities

    if known_services is None:
        known_services = async_get_all_services(hass)

    # Extract entities from trigger config
    for key in ("trigger", "triggers"):
        if key in config:
            entities.update(
                await extract_entities_from_trigger_config(
                    hass, config[key], known_services
                )
            )

    # Extract entities from condition config
    for key in ("condition", "conditions"):
        if key in config:
            entities.update(
                await extract_entities_from_condition_config(
                    hass, config[key], known_services
                )
            )

    # Extract entities from action config
    for key in ("action", "actions"):
        if key in config:
            entities.update(
                await async_extract_entities_from_action_config(
                    hass, config[key], known_services=known_services
                )
            )

    return entities


async def _entities_from_reference_fields(
    hass: HomeAssistant,
    config: dict[str, Any],
    known_services: set[str],
    *,
    in_values: bool = False,
) -> set[str]:
    """Extract entities from the config keys that name a reference.

    ``zone`` is in here because a zone trigger and a zone condition both name
    one, and it is read exactly like the others. So is the entity a numeric
    state trigger or condition takes as its threshold, unless the dictionary
    sits below a key that holds values: event data that only looks like one
    is still event data.
    """
    entities = set() if in_values else numeric_state_threshold_entities(config)
    for key in ("entity_id", "device_id", "zone"):
        if key in config:
            entities.update(
                await async_extract_entities_from_value(
                    hass, config[key], known_services=known_services
                )
            )
    return entities


async def extract_entities_from_trigger_config(
    hass: HomeAssistant,
    config: dict[str, Any] | list,
    known_services: set[str] | None = None,
    *,
    _in_values: bool = False,
) -> set[str]:
    """Extract entity IDs from trigger configuration."""
    entities = set()

    if not config:
        return entities

    if known_services is None:
        known_services = async_get_all_services(hass)

    if isinstance(config, list):
        for item in config:
            entities.update(
                await extract_entities_from_trigger_config(
                    hass, item, known_services, _in_values=_in_values
                )
            )
        return entities

    if not isinstance(config, dict):
        return entities

    entities.update(
        await _entities_from_reference_fields(
            hass, config, known_services, in_values=_in_values
        )
    )

    payload_keys = event_payload_keys_to_leave_alone(config)

    # Extract from nested configs
    for key, value in config.items():
        if key in payload_keys:
            continue

        if isinstance(value, (dict, list)):
            entities.update(
                await extract_entities_from_trigger_config(
                    hass,
                    value,
                    known_services,
                    _in_values=_in_values or key in VALUE_KEYS,
                )
            )

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
    hass: HomeAssistant,
    config: dict[str, Any] | list,
    known_services: set[str] | None = None,
    *,
    _in_values: bool = False,
) -> set[str]:
    """Extract entity IDs from condition configuration."""
    entities = set()

    if not config:
        return entities

    if known_services is None:
        known_services = async_get_all_services(hass)

    if isinstance(config, list):
        for item in config:
            entities.update(
                await extract_entities_from_condition_config(
                    hass, item, known_services, _in_values=_in_values
                )
            )
        return entities

    if not isinstance(config, dict):
        return entities

    entities.update(
        await _entities_from_reference_fields(
            hass, config, known_services, in_values=_in_values
        )
    )

    # Extract from nested configs
    for key, value in config.items():
        if isinstance(value, (dict, list)):
            entities.update(
                await extract_entities_from_condition_config(
                    hass,
                    value,
                    known_services,
                    _in_values=_in_values or key in VALUE_KEYS,
                )
            )

    return entities


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

    _known_entity_ids: set[str]
    _known_services: set[str]

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

    async def _async_named_in(self, config: dict[str, Any]) -> set[str]:
        """Return the entities a configuration names, the way this repair reads it.

        The same reading the report is built from, structure and templates
        alike, so comparing it with and without the disabled steps leaves out
        exactly what only those name.
        """
        named = await extract_entities_from_automation_config(
            self.hass, config, self._known_services
        )
        named |= await async_extract_entities_from_config(
            self.hass, without_never_rendered(config), self._known_services
        )
        return named

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown entity IDs referenced by ``entity`` (incl. templates)."""
        all_entities = core_references(entity, "entities")

        # Also extract entities directly from raw configuration if available
        if hasattr(entity, "raw_config") and entity.raw_config:
            all_entities.update(
                await extract_entities_from_automation_config(
                    self.hass, entity.raw_config, self._known_services
                )
            )
            for key in ("trigger", "triggers"):
                all_entities.difference_update(
                    extract_event_types_from_trigger_config(entity.raw_config.get(key))
                )

        # Extract entities from Template objects within the automation entity
        all_entities.update(
            await extract_template_entities_from_automation_entity(
                self.hass, entity, self._known_services
            )
        )

        if isinstance(raw_config := getattr(entity, "raw_config", None), dict):
            named = await self._async_named_in(raw_config)

            # Home Assistant's own list takes the `entity_id` of somebody's
            # own event too, which is data from the sender, and the made-up
            # entity `logbook.log` files an entry under. Neither has to exist.
            # Left out, unless this repair finds it named somewhere else too.
            all_entities -= harmless_entity_mentions(raw_config) - named

            # It includes disabled steps, triggers and conditions too.
            # Something parked that way does nothing, so what only it names is
            # left out of the report: whatever this repair finds in the
            # configuration, and no longer finds once those are pruned.
            # Home Assistant's own list also reads keys this repair does not,
            # like the `at` of a time trigger. Whatever only a disabled part
            # holds goes as well, whichever key it sits under.
            still_named = await self._async_named_in(without_disabled_steps(raw_config))
            all_entities -= (
                named | mentioned_only_in_disabled_steps(raw_config)
            ) - still_named

        unknown = await async_filter_known_entity_ids_with_templates(
            self.hass,
            entity_ids=all_entities,
            known_entity_ids=self._known_entity_ids,
            known_services=self._known_services,
        )

        # Where an entity ID goes, something that is no entity ID at all finds
        # nothing, whatever exists. Listed with the rest, said apart.
        if isinstance(raw_config, dict):
            unknown |= extract_not_entity_ids_from_config(self.hass, raw_config)

        return unknown
