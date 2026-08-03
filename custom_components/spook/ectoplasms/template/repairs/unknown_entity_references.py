"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_STATE_CHANGED
from homeassistant.core import Event, callback
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair
from ....template_extraction import async_extract_entities_from_config

if TYPE_CHECKING:
    from collections.abc import Mapping


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds unknown entities referenced in template helpers.

    Template helper config entries store their templates in the entry
    options; a template referencing a removed entity resolves to
    ``unknown`` and is otherwise silent.
    """

    domain = "template"
    repair = "template_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = "template"
    inspect_on_reload = "template"
    automatically_clean_up_issues = True

    async def async_activate(self) -> None:
        """Activate the repair."""
        await super().async_activate()

        @callback
        def _state_entity_changed(event_data: Mapping[str, Any]) -> bool:
            """Return if a state entity was added or removed."""
            return (
                event_data.get("old_state") is None
                or event_data.get("new_state") is None
            )

        @callback
        def _async_call_inspect_debouncer(_: Event) -> None:
            """Trigger an inspection when a state entity is added or removed."""
            self.inspect_debouncer.async_schedule_call()

        self._event_subs.add(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                _async_call_inspect_debouncer,
                event_filter=_state_entity_changed,
            ),
        )

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass, include_all_none=True)

        for entry in self.hass.config_entries.async_entries(self.domain):
            self.possible_issue_ids.add(entry.entry_id)

            referenced = await async_extract_entities_from_config(
                self.hass, dict(entry.options)
            )
            if unknown_entities := async_filter_known_entity_ids(
                self.hass,
                referenced,
                known_entity_ids=known_entity_ids,
            ):
                self.async_create_issue(
                    issue_id=entry.entry_id,
                    translation_placeholders={
                        "entities": async_describe_unknown_entities(
                            self.hass, sorted(unknown_entities)
                        ),
                        "helper": entry.title,
                        "edit": "/config/helpers",
                    },
                )
