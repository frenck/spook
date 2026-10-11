"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import script
from homeassistant.const import EVENT_COMPONENT_LOADED

from ....never_true_templates import never_true_templates
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find templates in scripts that can never pass.

    A template condition, a `wait_template`, the `while` or `until` of a
    repeat, written so that it can never render what it needs, loads fine
    and never passes, and Home Assistant says nothing. Only the template's
    own text is read, so looking again after a reload is enough. A script
    that failed to load is left alone: Home Assistant reports that one itself.
    """

    domain = script.DOMAIN
    repair = "script_never_true_templates"
    inspect_events = {EVENT_COMPONENT_LOADED}
    inspect_on_reload = True

    unavailable_entity_class = script.UnavailableScriptEntity
    entity_label = "script"
    reference_label = "templates"
    edit_url_pattern = "/config/script/edit/{unique_id}"

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return the templates in ``entity`` that can never pass."""
        if not (raw_config := getattr(entity, "raw_config", None)):
            return set()
        return never_true_templates(self.hass, self.domain, raw_config)
