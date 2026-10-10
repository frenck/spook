"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import script
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....repairs import AbstractSpookUnknownAttributesRepair


class SpookRepair(AbstractSpookUnknownAttributesRepair):
    """Spook repair tries to find unknown attributes used in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_attribute_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True

    unavailable_entity_class = script.UnavailableScriptEntity
    entity_label = "script"
    edit_url_pattern = "/config/script/edit/{unique_id}"
