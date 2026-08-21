"""Spook - Your homie."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_RESTORED,
    EVENT_COMPONENT_LOADED,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import Event, State


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds registered entities that no longer exist.

    A registry entry whose integration loaded but never provided the
    entity this session gets a restored ``unavailable`` state. Grouped per
    config entry, and only for config entries that finished loading, so a
    slow or retrying integration is never mistaken for a dead entity.
    """

    domain = "homeassistant"
    repair = "dead_entities"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    automatically_clean_up_issues = True

    async def async_activate(self) -> None:
        """Handle activating the repair."""
        await super().async_activate()

        # The restored placeholder state can appear and disappear without
        # anything else saying so. An entity removed while its registry entry
        # survives gets one written for it, and an entity that finally shows
        # up overwrites the one it had. Neither touches the entity registry,
        # and the config entry stays loaded throughout, so the events above
        # only catch this at startup or by coincidence.
        #
        # Watched by the restored flag flipping rather than by entities being
        # added or removed: crossing into or out of that placeholder is the
        # entire signal this repair reads, and it is not something an ordinary
        # state change does.
        @callback
        def _restored_flag_changed(event_data: Mapping[str, Any]) -> bool:
            """Return if an entity entered or left the restored state."""

            def is_restored(state: State | None) -> bool:
                return bool(state and state.attributes.get(ATTR_RESTORED))

            return is_restored(event_data.get("old_state")) != is_restored(
                event_data.get("new_state")
            )

        @callback
        def _async_call_inspect_debouncer(_: Event) -> None:
            """Trigger an inspection when the restored flag flips."""
            self.inspect_debouncer.async_schedule_call()

        self._event_subs.add(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                _async_call_inspect_debouncer,
                event_filter=_restored_flag_changed,
            ),
        )

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        entity_registry = er.async_get(self.hass)

        dead_by_entry: dict[str, list[str]] = defaultdict(list)
        for state in self.hass.states.async_all():
            if state.state != STATE_UNAVAILABLE or not state.attributes.get(
                ATTR_RESTORED
            ):
                continue
            entry = entity_registry.async_get(state.entity_id)
            if entry is None or entry.config_entry_id is None:
                # Only config-entry-backed entities can be confirmed dead by
                # cross-checking their config entry's load state.
                continue
            dead_by_entry[entry.config_entry_id].append(state.entity_id)

        for entry_id, entity_ids in dead_by_entry.items():
            config_entry = self.hass.config_entries.async_get_entry(entry_id)
            if (
                config_entry is None
                or config_entry.state is not ConfigEntryState.LOADED
            ):
                # The integration is gone or still (re)loading; its entities
                # may still appear, so this is not a dead-entity signal.
                continue

            self.possible_issue_ids.add(entry_id)
            self.async_create_issue(
                issue_id=entry_id,
                issue_domain=config_entry.domain,
                translation_placeholders={
                    "integration": config_entry.title,
                    "entities": "\n".join(
                        f"- `{entity_id}`" for entity_id in sorted(entity_ids)
                    ),
                },
            )
