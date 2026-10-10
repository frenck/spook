"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.const import EVENT_COMPONENT_LOADED

from ....trigger_ids import unknown_trigger_ids
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookAutomationReferencesRepair):
    """Spook repair tries to find trigger IDs no trigger of the automation has.

    A trigger condition asking for such an ID can never match, so the branch
    behind it never runs. Home Assistant loads it without complaint. All of
    it is in the automation's own configuration, so looking again after a
    reload is enough.

    Read from the configuration as written, which for an automation on a
    blueprint is the one with its inputs filled in. An automation that
    failed to load is left alone: its triggers never run at all, and Home
    Assistant says so itself.
    """

    domain = automation.DOMAIN
    repair = "automation_unknown_trigger_id_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        EVENT_COMPONENT_LOADED,
    }
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "trigger_ids"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return the trigger IDs ``entity`` checks for that it never has."""
        if not (raw_config := getattr(entity, "raw_config", None)):
            return set()
        return unknown_trigger_ids(raw_config)
