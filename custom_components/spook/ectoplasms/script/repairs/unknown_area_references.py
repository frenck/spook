"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import script
from homeassistant.helpers import area_registry as ar

from ....entity_filtering import async_filter_known_area_ids, async_get_all_area_ids
from ....reference_extraction import extract_targets_from_config
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced areas in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_area_references"
    inspect_events = {ar.EVENT_AREA_REGISTRY_UPDATED}
    inspect_on_reload = True

    unavailable_entity_class = script.UnavailableScriptEntity
    entity_label = "script"
    reference_label = "areas"
    edit_url_pattern = "/config/script/edit/{unique_id}"

    _known_area_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known area IDs for this inspection cycle."""
        self._known_area_ids = async_get_all_area_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown area IDs referenced by ``entity``."""
        area_ids = set(entity.script.referenced_areas)

        # Also walk the raw configuration; the built-in extraction misses
        # references nested in some step types, like repeat sequences.
        if raw_config := getattr(entity, "raw_config", None):
            area_ids.update(extract_targets_from_config(raw_config).area_ids)

        return async_filter_known_area_ids(
            self.hass,
            area_ids=area_ids,
            known_area_ids=self._known_area_ids,
        )
