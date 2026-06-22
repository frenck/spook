"""Spook - Your homie."""

from __future__ import annotations

from typing import Any

from homeassistant.components import automation
from homeassistant.helpers import device_registry as dr

from ....entity_filtering import async_filter_known_device_ids, async_get_all_device_ids
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair


def extract_event_data_device_ids_from_trigger_config(
    config: dict[str, Any] | list,
) -> set[str]:
    """Extract device IDs from event trigger data."""
    device_ids = set()

    if not config:
        return device_ids

    if isinstance(config, list):
        for item in config:
            device_ids.update(extract_event_data_device_ids_from_trigger_config(item))
        return device_ids

    if not isinstance(config, dict):
        return device_ids

    if config.get("platform", config.get("trigger")) == "event" and isinstance(
        event_data := config.get("event_data"), dict
    ):
        value = event_data.get("device_id")
        if isinstance(value, str):
            device_ids.add(value)
        elif isinstance(value, list):
            device_ids.update(item for item in value if isinstance(item, str))

    for value in config.values():
        if isinstance(value, (dict, list)):
            device_ids.update(extract_event_data_device_ids_from_trigger_config(value))

    return device_ids


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced devices in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_device_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        dr.EVENT_DEVICE_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "devices"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    _known_device_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known device IDs for this inspection cycle."""
        self._known_device_ids = async_get_all_device_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown device IDs referenced by ``entity``."""
        device_ids = set(entity.referenced_devices)

        if hasattr(entity, "raw_config") and entity.raw_config:
            device_ids.difference_update(
                extract_event_data_device_ids_from_trigger_config(
                    entity.raw_config.get("trigger")
                )
            )

        return async_filter_known_device_ids(
            self.hass,
            device_ids=device_ids,
            known_device_ids=self._known_device_ids,
        )
