"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.helpers import area_registry as ar, floor_registry as fr

from ....entity_filtering import (
    TemplateFloorLookup,
    async_get_all_floor_ids,
    async_get_template_floor_lookup,
    filter_known_floor_ids,
)
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from ....repairs import InspectedEntity


class SpookRepair(AbstractSpookAutomationReferencesRepair):
    """Spook repair tries to find unknown referenced floors in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_floor_references"
    # Templates look floors up through areas as well, so a renamed area
    # can change what they find.
    inspect_events = {
        ar.EVENT_AREA_REGISTRY_UPDATED,
        fr.EVENT_FLOOR_REGISTRY_UPDATED,
    }
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "floors"
    edit_url_pattern = "/config/automation/edit/{unique_id}"
    core_reference_kind = "floors"

    _known_floor_ids: set[str]
    _template_lookup: TemplateFloorLookup

    async def _async_setup_inspection(self) -> None:
        """Cache known floor IDs for this inspection cycle."""
        self._known_floor_ids = async_get_all_floor_ids(self.hass)
        # What the floor lookups in templates resolve against, snapshotted
        # on the event loop, so the computation in the executor can decide
        # what they find without reaching back for the registries.
        self._template_lookup = async_get_template_floor_lookup(self.hass)

    def _compute_unknown_references(self, entity: InspectedEntity) -> set[str]:
        """Return unknown floor IDs referenced by ``entity``."""
        return self._compute_unknown_references_from_config(
            entity,
            kind="floors",
            not_found=self._template_lookup.not_found,
            known_ids=self._known_floor_ids,
            filter_known=filter_known_floor_ids,
        )
