"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import script
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import trigger as trigger_helper

from ....platform_validation import async_filter_unknown_trigger_keys
from ....reference_extraction import extract_platform_keys_from_config
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown trigger types in scripts.

    A script using a trigger from a removed integration fails validation
    entirely and becomes unavailable; Home Assistant only raises a
    generic issue for it. This repair names the exact trigger.
    Unavailable scripts are deliberately inspected: they are the broken
    ones.
    """

    domain = script.DOMAIN
    repair = "script_unknown_trigger_references"
    inspect_events = {EVENT_COMPONENT_LOADED}
    inspect_on_reload = True

    entity_label = "script"
    reference_label = "triggers"
    edit_url_pattern = "/config/script/edit/{unique_id}"

    async def async_activate(self) -> None:
        """Activate the repair."""
        await super().async_activate()

        async def _async_platforms_registered(_platforms: set[str]) -> None:
            """Re-inspect when new trigger platforms register."""
            self.inspect_debouncer.async_schedule_call()

        self._event_subs.add(
            trigger_helper.async_subscribe_platform_events(
                self.hass,
                _async_platforms_registered,
            ),
        )

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown trigger keys used by ``entity``."""
        if not (raw_config := getattr(entity, "raw_config", None)):
            return set()

        return await async_filter_unknown_trigger_keys(
            self.hass,
            extract_platform_keys_from_config(raw_config).trigger_keys,
        )
