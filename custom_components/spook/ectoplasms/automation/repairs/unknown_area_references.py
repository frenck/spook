"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.helpers import area_registry as ar

from ....entity_filtering import (
    TemplateAreaLookup,
    async_get_all_area_ids,
    async_get_template_area_lookup,
    filter_known_area_ids,
)
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from ....repairs import InspectedEntity


class SpookRepair(AbstractSpookAutomationReferencesRepair):
    """Spook repair tries to find unknown referenced areas in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_area_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
    }
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "areas"
    edit_url_pattern = "/config/automation/edit/{unique_id}"
    core_reference_kind = "areas"

    _known_area_ids: set[str]
    _template_lookup: TemplateAreaLookup

    async def _async_setup_inspection(self) -> None:
        """Cache known area IDs for this inspection cycle."""
        self._known_area_ids = async_get_all_area_ids(self.hass)
        # What the area lookups in templates resolve against, snapshotted
        # on the event loop, so the computation in the executor can decide
        # what they find without reaching back for the registry.
        self._template_lookup = async_get_template_area_lookup(self.hass)

    def _compute_unknown_references(self, entity: InspectedEntity) -> set[str]:
        """Return unknown area IDs referenced by ``entity``."""
        return self._compute_unknown_references_from_config(
            entity,
            kind="areas",
            not_found=self._template_lookup.not_found,
            known_ids=self._known_area_ids,
            filter_known=filter_known_area_ids,
        )
