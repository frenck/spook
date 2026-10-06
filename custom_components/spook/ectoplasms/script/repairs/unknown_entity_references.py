"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import script
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....action_extraction import (
    async_extract_entities_from_action_config,
    async_extract_entities_only_in_disabled_steps,
)
from ....entity_filtering import async_get_all_entity_ids, async_get_all_services
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair
from ....template_extraction import (
    async_extract_entities_from_config,
    async_filter_known_entity_ids_with_templates,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def extract_entities_from_trigger_config(config: dict[str, Any] | list) -> set[str]:
    """Extract entity IDs from a trigger config."""
    entities = set()

    if not config:
        return entities

    if isinstance(config, list):
        for item in config:
            entities.update(extract_entities_from_trigger_config(item))
        return entities

    if not isinstance(config, dict):
        return entities

    # Extract entity_id from trigger config
    if "entity_id" in config:
        entity_id = config["entity_id"]
        if isinstance(entity_id, str):
            entities.add(entity_id)
        elif isinstance(entity_id, list):
            entities.update([e for e in entity_id if isinstance(e, str)])

    # Recursively process nested configs
    for value in config.values():
        if isinstance(value, (dict, list)):
            entities.update(extract_entities_from_trigger_config(value))

    return entities


def extract_referenced_entities_from_script(entity: script.ScriptEntity) -> set[str]:
    """Return entity references from a script entity."""
    try:
        return set(entity.script.referenced_entities)
    except TypeError as err:
        if str(err) != "unhashable type: 'dict'":
            raise
        return set()


async def extract_template_entities_from_script_entity(
    hass: HomeAssistant,
    entity: Any,
    known_services: set[str] | None = None,
) -> set[str]:
    """Extract entities from script configuration using Template analysis.

    This function finds template strings in script configuration and creates
    Template objects to extract entity references using Template.async_render_to_info().
    This provides more comprehensive entity detection than regex-based parsing alone.

    ``known_services`` is built once per inspection and handed down, because
    building it flattens every service Home Assistant has and every script
    with a template in it needs the same answer.

    Read from the configuration as written, like the automation repair does.
    The script helper underneath keeps no configuration of its own, so this
    used to find nothing at all.
    """
    if not (config := getattr(entity, "raw_config", None)):
        return set()

    return await async_extract_entities_from_config(hass, config, known_services)


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced entity in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True

    unavailable_entity_class = script.UnavailableScriptEntity
    entity_label = "script"
    reference_label = "entities"
    references_are_entities = True
    edit_url_pattern = "/config/script/edit/{unique_id}"

    _known_entity_ids: set[str]
    _known_services: set[str]

    def _get_blueprint_trigger_entities(self, entity: script.ScriptEntity) -> set[str]:
        """Extract entity references from blueprint trigger inputs."""
        entities = set()

        if (
            not hasattr(entity, "referenced_blueprint")
            or not entity.referenced_blueprint
        ):
            return entities

        config = getattr(entity, "raw_config", None)
        if not config or not isinstance(config, dict) or "use_blueprint" not in config:
            return entities

        blueprint_config = config["use_blueprint"]
        if "input" not in blueprint_config:
            return entities

        input_config = blueprint_config["input"]
        # Look for inputs that might contain triggers (like discard_when)
        for value in input_config.values():
            if isinstance(value, (dict, list)) and "trigger" in str(value):
                trigger_entities = extract_entities_from_trigger_config(value)
                if trigger_entities:
                    entities.update(trigger_entities)

        return entities

    async def _async_setup_inspection(self) -> None:
        """Cache what every script in this cycle needs looked up.

        The service set is in here for the same reason as the entity ids:
        building it flattens every service Home Assistant has, and it is the
        same answer for every script in one pass.
        """
        self._known_entity_ids = async_get_all_entity_ids(
            self.hass, include_all_none=True
        )
        self._known_services = async_get_all_services(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown entity IDs referenced by ``entity`` (incl. templates)."""
        # Get all referenced entities from the script
        all_entities = extract_referenced_entities_from_script(entity)

        # Check for blueprint trigger inputs
        all_entities.update(self._get_blueprint_trigger_entities(entity))

        # Home Assistant's own list leaves out entities handed over as action
        # data, like `entity: light.kitchen` in a call to another script. The
        # automation repair reads those from the configuration as written, and
        # so does this one.
        if isinstance(raw_config := getattr(entity, "raw_config", None), dict):
            all_entities.update(
                await async_extract_entities_from_action_config(
                    self.hass,
                    raw_config.get("sequence") or [],
                    known_services=self._known_services,
                )
            )

        # Extract entities from Template objects within the script entity
        all_entities.update(
            await extract_template_entities_from_script_entity(
                self.hass, entity, self._known_services
            )
        )

        # Home Assistant's own list includes disabled steps too. A step parked
        # that way does nothing, so what only it names is left out.
        if isinstance(raw_config, dict):
            all_entities -= await async_extract_entities_only_in_disabled_steps(
                self.hass,
                raw_config,
                ("sequence",),
                known_services=self._known_services,
            )

        return await async_filter_known_entity_ids_with_templates(
            self.hass,
            entity_ids=all_entities,
            known_entity_ids=self._known_entity_ids,
            known_services=self._known_services,
        )
