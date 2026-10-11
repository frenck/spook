"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.auth import EVENT_USER_ADDED, EVENT_USER_REMOVED
from homeassistant.components import automation
from homeassistant.const import EVENT_COMPONENT_LOADED

from ....user_references import async_get_user_ids, extract_user_ids_from_config
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookAutomationReferencesRepair):
    """Spook repair tries to find users in automations that no longer exist.

    An event trigger waiting for a user, or a template comparing the user
    behind something with an ID, never matches a user that was removed.
    Home Assistant loads it without a word, and the part it guards quietly
    never runs for anybody.
    """

    domain = automation.DOMAIN
    repair = "automation_unknown_user_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        EVENT_COMPONENT_LOADED,
        EVENT_USER_ADDED,
        EVENT_USER_REMOVED,
    }
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "users"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    _known_user_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache the users there are for this inspection cycle."""
        self._known_user_ids = await async_get_user_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return the users ``entity`` names that no longer exist."""
        if not (raw_config := getattr(entity, "raw_config", None)):
            return set()
        return extract_user_ids_from_config(raw_config) - self._known_user_ids
