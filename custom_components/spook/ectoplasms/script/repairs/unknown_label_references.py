"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import script
from homeassistant.helpers import label_registry as lr

from ....entity_filtering import async_filter_known_label_ids, async_get_all_label_ids
from ....reference_extraction import extract_targets_from_config
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced labels in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_label_references"
    inspect_events = {lr.EVENT_LABEL_REGISTRY_UPDATED}
    inspect_on_reload = True

    unavailable_entity_class = script.UnavailableScriptEntity
    entity_label = "script"
    reference_label = "labels"
    edit_url_pattern = "/config/script/edit/{unique_id}"

    _known_label_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known label IDs for this inspection cycle."""
        self._known_label_ids = async_get_all_label_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown label IDs referenced by ``entity``."""
        label_ids = set(entity.script.referenced_labels)

        # Also walk the raw configuration; the built-in extraction misses
        # references nested in some step types, like repeat sequences.
        if raw_config := getattr(entity, "raw_config", None):
            label_ids.update(extract_targets_from_config(raw_config).label_ids)

        return async_filter_known_label_ids(
            self.hass,
            label_ids=label_ids,
            known_label_ids=self._known_label_ids,
        )
