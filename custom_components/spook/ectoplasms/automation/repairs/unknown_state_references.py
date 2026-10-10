"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import automation
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....repairs import AbstractSpookUnknownStatesRepair
from . import AbstractSpookAutomationReferencesRepair


class SpookRepair(
    AbstractSpookUnknownStatesRepair, AbstractSpookAutomationReferencesRepair
):
    """Spook repair tries to find unknown states used in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_state_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_entity_added_or_removed = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    edit_url_pattern = "/config/automation/edit/{unique_id}"
