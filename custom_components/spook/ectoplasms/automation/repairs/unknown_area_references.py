"""Spook - Your homie."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.helpers import area_registry as ar

from ....entity_filtering import async_filter_known_area_ids, async_get_all_area_ids
from ....reference_extraction import (
    async_raw_config_references,
    core_references,
    only_in_disabled_steps,
)
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from typing import Any


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

    _known_area_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known area IDs for this inspection cycle."""
        self._known_area_ids = async_get_all_area_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown area IDs referenced by ``entity``."""
        area_ids = core_references(entity, "areas")

        # Also walk the raw configuration; the built-in extraction misses
        # references nested in some step types, like repeat sequences.
        if raw_config := getattr(entity, "raw_config", None):
            # Templates that look up an area that is not there are read too.
            references = partial(async_raw_config_references, self.hass, kind="areas")
            area_ids.update(references(raw_config))
            # A disabled step does nothing, so what only it names is left out.
            # Read the same way, or a template there still counts.
            area_ids -= only_in_disabled_steps(raw_config, references)

        return async_filter_known_area_ids(
            self.hass,
            area_ids=area_ids,
            known_area_ids=self._known_area_ids,
        )
