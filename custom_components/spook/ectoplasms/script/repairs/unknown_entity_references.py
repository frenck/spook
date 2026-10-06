"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import script
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....action_extraction import async_extract_entities_from_action_config
from ....entity_filtering import async_get_all_entity_ids, async_get_all_services
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair
from ....template_extraction import (
    async_extract_entities_from_config,
    async_filter_known_entity_ids_with_templates,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


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

        return await async_filter_known_entity_ids_with_templates(
            self.hass,
            entity_ids=all_entities,
            known_entity_ids=self._known_entity_ids,
            known_services=self._known_services,
        )
