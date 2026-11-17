"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import automation
from homeassistant.helpers import device_registry as dr

from ....entity_filtering import async_get_all_device_ids, filter_known_device_ids
from ....reference_extraction import (
    extract_targets_from_config,
    names_given_to_templates,
    only_in_disabled_steps,
)
from ....template_extraction import extract_device_ids_from_config
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from ....repairs import InspectedEntity


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


class SpookRepair(AbstractSpookAutomationReferencesRepair):
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
    core_reference_kind = "devices"

    _known_device_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known device IDs for this inspection cycle."""
        self._known_device_ids = async_get_all_device_ids(self.hass)

    def _compute_unknown_references(self, entity: InspectedEntity) -> set[str]:
        """Return unknown device IDs referenced by ``entity``."""
        device_ids = entity.core_references()

        if raw_config := entity.raw_config:
            # Also walk the raw configuration; the built-in extraction misses
            # references nested in some step types, like repeat sequences.
            # The walker never collects from event trigger payloads, so the
            # subtraction below only affects built-in extraction results.
            device_ids.update(extract_targets_from_config(raw_config).device_ids)
            device_ids.difference_update(
                extract_event_data_device_ids_from_trigger_config(
                    raw_config.get("trigger")
                )
            )
            device_ids.difference_update(
                extract_event_data_device_ids_from_trigger_config(
                    raw_config.get("triggers")
                )
            )
            # Devices referenced through the device functions in templates.
            # The variables and fields it gives its templates hide a call.
            shadowed = names_given_to_templates(raw_config)
            device_ids.update(extract_device_ids_from_config(raw_config, shadowed))
            # A disabled step does nothing, so what only it names is left out.
            device_ids -= only_in_disabled_steps(
                raw_config,
                lambda found: (
                    extract_targets_from_config(found).device_ids
                    | extract_device_ids_from_config(found, shadowed)
                ),
            )

        return filter_known_device_ids(device_ids, self._known_device_ids)
