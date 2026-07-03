"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import script
from homeassistant.helpers import device_registry as dr

from ....entity_filtering import async_filter_known_device_ids, async_get_all_device_ids
from ....reference_extraction import extract_targets_from_config
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced devices in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_device_references"
    inspect_events = {dr.EVENT_DEVICE_REGISTRY_UPDATED}
    inspect_config_entry_changed = True
    inspect_on_reload = True

    unavailable_entity_class = script.UnavailableScriptEntity
    entity_label = "script"
    reference_label = "devices"
    edit_url_pattern = "/config/script/edit/{unique_id}"

    _known_device_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known device IDs for this inspection cycle."""
        self._known_device_ids = async_get_all_device_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown device IDs referenced by ``entity``."""
        device_ids = set(entity.script.referenced_devices)

        # Also walk the raw configuration; the built-in extraction misses
        # references nested in some step types, like repeat sequences.
        if raw_config := getattr(entity, "raw_config", None):
            device_ids.update(extract_targets_from_config(raw_config).device_ids)

        return async_filter_known_device_ids(
            self.hass,
            device_ids=device_ids,
            known_device_ids=self._known_device_ids,
        )
