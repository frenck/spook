"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.auth import EVENT_USER_ADDED, EVENT_USER_REMOVED
from homeassistant.components import script
from homeassistant.const import EVENT_COMPONENT_LOADED

from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair
from ....user_references import async_get_user_ids, extract_user_ids_from_config

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find users in scripts that no longer exist.

    A script is handed the context it was started with, so it can do one
    thing for one user and another for the rest. A template comparing that
    user with one that was removed never matches, and an event the script
    waits for never comes from that user. Home Assistant does not say so.
    """

    domain = script.DOMAIN
    repair = "script_unknown_user_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_USER_ADDED,
        EVENT_USER_REMOVED,
    }
    inspect_on_reload = True

    unavailable_entity_class = script.UnavailableScriptEntity
    entity_label = "script"
    reference_label = "users"
    edit_url_pattern = "/config/script/edit/{unique_id}"

    _known_user_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache the users there are for this inspection cycle."""
        self._known_user_ids = await async_get_user_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return the users ``entity`` names that no longer exist."""
        if not (raw_config := getattr(entity, "raw_config", None)):
            return set()
        return extract_user_ids_from_config(raw_config) - self._known_user_ids
