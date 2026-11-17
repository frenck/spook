"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import script
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....action_extraction import (
    extract_entities_from_action_config,
    unknown_entities_named,
)
from ....entity_filtering import async_get_all_entity_ids, async_get_all_services
from ....reference_extraction import (
    names_given_to_templates,
    without_never_rendered,
)
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair
from ....template_extraction import _extract_entities_from_config

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import Service

    from ....repairs import InspectedEntity


def extract_template_entities_from_config(
    raw_config: Any,
    known_services: set[str],
) -> set[str]:
    """Extract the entities the templates in a raw configuration name.

    Every template string in it, read the way
    `template_extraction._extract_entities_from_config` reads them.

    ``known_services`` is built once per inspection and handed down, because
    building it flattens every service Home Assistant has and every script
    with a template in it needs the same answer.

    Read from the configuration as written, like the automation repair does.
    The script helper underneath keeps no configuration of its own, so this
    used to find nothing at all.
    """
    if not raw_config:
        return set()

    # A description, a name or a field example is shown, never rendered: an
    # entity in an example template there is not one the script uses.
    return _extract_entities_from_config(
        without_never_rendered(raw_config),
        known_services,
        names_given_to_templates(raw_config),
    )


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
    core_reference_kind = "entities"

    _known_entity_ids: set[str]
    _known_services: set[str]
    _services: Mapping[str, Mapping[str, Service]]

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
        # The registry itself, for telling what an action hands over as an
        # `entity_id` that is no entity ID: read on the event loop, so the
        # computation in the executor never has to reach back for it.
        self._services = self.hass.services.async_services()

    def _named_in(self, config: dict[str, Any], shadowed: frozenset[str]) -> set[str]:
        """Return the entities a configuration names, the way this repair reads it.

        The same reading the report is built from, the steps and templates
        alike, so comparing it with and without the disabled steps leaves out
        exactly what only those name. ``shadowed`` comes from the whole
        configuration, as `config` can be one without its disabled steps.
        """
        steps = config.get("sequence") or []
        named = extract_entities_from_action_config(
            # A single step can be written without a list.
            [steps] if isinstance(steps, dict) else steps,
            known_services=self._known_services,
            shadowed=shadowed,
        )
        named |= _extract_entities_from_config(
            without_never_rendered(config),
            self._known_services,
            shadowed,
        )
        return named

    def _compute_unknown_references(self, entity: InspectedEntity) -> set[str]:
        """Return unknown entity IDs referenced by ``entity`` (incl. templates)."""
        # Get all referenced entities from the script
        all_entities = entity.core_references()

        # Home Assistant's own list leaves out entities handed over as action
        # data, like `entity: light.kitchen` in a call to another script. The
        # automation repair reads those from the configuration as written, and
        # so does this one.
        raw_config = entity.raw_config
        if isinstance(raw_config, dict):
            all_entities.update(
                extract_entities_from_action_config(
                    raw_config.get("sequence") or [],
                    known_services=self._known_services,
                    shadowed=names_given_to_templates(raw_config),
                )
            )

        # Extract entities from the templates within the configuration
        all_entities.update(
            extract_template_entities_from_config(raw_config, self._known_services)
        )

        return unknown_entities_named(
            all_entities,
            raw_config,
            named_in=self._named_in,
            known_entity_ids=self._known_entity_ids,
            known_services=self._known_services,
            services=self._services,
        )
