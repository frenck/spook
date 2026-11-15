"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.helpers import label_registry as lr

from ....entity_filtering import (
    TemplateLabelLookup,
    async_get_all_label_ids,
    async_get_template_label_lookup,
    filter_known_label_ids,
)
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from ....repairs import InspectedEntity


class SpookRepair(AbstractSpookAutomationReferencesRepair):
    """Spook repair tries to find unknown referenced labels in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_label_references"
    inspect_events = {
        lr.EVENT_LABEL_REGISTRY_UPDATED,
    }
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "labels"
    edit_url_pattern = "/config/automation/edit/{unique_id}"
    core_reference_kind = "labels"

    _known_label_ids: set[str]
    _template_lookup: TemplateLabelLookup

    async def _async_setup_inspection(self) -> None:
        """Cache known label IDs for this inspection cycle."""
        self._known_label_ids = async_get_all_label_ids(self.hass)
        # What the label lookups in templates resolve against, snapshotted
        # on the event loop, so the computation in the executor can decide
        # what they find without reaching back for the registry.
        self._template_lookup = async_get_template_label_lookup(self.hass)

    def _compute_unknown_references(self, entity: InspectedEntity) -> set[str]:
        """Return unknown label IDs referenced by ``entity``."""
        return self._compute_unknown_references_from_config(
            entity,
            kind="labels",
            not_found=self._template_lookup.not_found,
            known_ids=self._known_label_ids,
            filter_known=filter_known_label_ids,
        )
