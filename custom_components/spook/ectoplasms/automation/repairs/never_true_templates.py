"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.const import EVENT_COMPONENT_LOADED

from ....never_true_templates import never_true_templates
from ....reference_extraction import config_to_judge
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookAutomationReferencesRepair):
    """Spook repair tries to find templates in automations that can never pass.

    A template condition passes only on `true`, a template trigger only on
    something that reads as true. One written so that it can never render
    that, like text in quotes or without any `{{ }}`, loads fine and never
    passes, and Home Assistant says nothing. Only the template's own text is
    read, so looking again after a reload is enough.

    Read from the configuration as written, which for an automation on a
    blueprint is the one with its inputs filled in. An automation that
    failed to load is left alone: Home Assistant reports that one itself.
    """

    domain = automation.DOMAIN
    repair = "automation_never_true_templates"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        EVENT_COMPONENT_LOADED,
    }
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "templates"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return the templates in ``entity`` that can never pass."""
        if not (raw_config := getattr(entity, "raw_config", None)):
            return set()
        return never_true_templates(
            self.hass, self.domain, config_to_judge(entity, raw_config)
        )
