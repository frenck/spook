"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.helpers import area_registry as ar, floor_registry as fr

from ....entity_filtering import async_filter_known_floor_ids, async_get_all_floor_ids
from ....reference_extraction import (
    async_raw_config_references,
    core_references,
    extract_targets_from_config,
    only_in_disabled_steps,
)
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from typing import Any


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

    _known_floor_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known floor IDs for this inspection cycle."""
        self._known_floor_ids = async_get_all_floor_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown floor IDs referenced by ``entity``."""
        floor_ids = core_references(entity, "floors")

        # Also walk the raw configuration; the built-in extraction misses
        # references nested in some step types, like repeat sequences.
        if raw_config := getattr(entity, "raw_config", None):
            # Templates that look up a floor that is not there are read too.
            floor_ids.update(
                async_raw_config_references(self.hass, raw_config, "floors")
            )
            # A disabled step does nothing, so what only it names is left out.
            floor_ids -= only_in_disabled_steps(
                raw_config, lambda found: extract_targets_from_config(found).floor_ids
            )

        return async_filter_known_floor_ids(
            self.hass,
            floor_ids=floor_ids,
            known_floor_ids=self._known_floor_ids,
        )
