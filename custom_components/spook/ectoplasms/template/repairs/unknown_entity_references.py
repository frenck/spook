"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_STATE_CHANGED
from homeassistant.core import Event, callback
from homeassistant.helpers import entity_registry as er

from ....action_extraction import async_extract_entities_from_action_config
from ....const import LOGGER
from ....entity_filtering import (
    async_filter_known_entity_ids,
    async_get_all_entity_ids,
    async_get_all_services,
)
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
        known_services = async_get_all_services(self.hass)

        for entry in self.hass.config_entries.async_entries(self.domain):
            self.possible_issue_ids.add(entry.entry_id)

            options = dict(entry.options)
            referenced = await async_extract_entities_from_config(
                self.hass, options, known_services
            )

            # Template helpers can also run action sequences: a button's press,
            # a switch's turn_on/turn_off, a cover's open/close, an alarm's
            # arm/disarm and so on. Those reference entities through structured
            # config (target, entity_id, service data) rather than through Jinja,
            # so the template extraction above does not see them.
            #
            # Extracting the actions twice separates references that a step
            # carrying `enabled: false` is the only source of: those cannot
            # break a run, so the report says so instead of listing them
            # alongside the ones that can.
            active = set(referenced)
            for option in options.values():
                # Only structured options can hold an action; a plain string
                # option walks straight back out of the extractor.
                if not isinstance(option, (dict, list)):
                    continue

                referenced |= await async_extract_entities_from_action_config(
                    self.hass, option, known_services=known_services
                )
                active |= await async_extract_entities_from_action_config(
                    self.hass,
                    option,
                    include_disabled=False,
                    known_services=known_services,
                )

            if unknown_entities := async_filter_known_entity_ids(
                self.hass,
                referenced,
                known_entity_ids=known_entity_ids,
            ):
                unknown_active = async_filter_known_entity_ids(
                    self.hass,
                    active,
                    known_entity_ids=known_entity_ids,
                )
                self.async_create_issue(
                    issue_id=entry.entry_id,
                    translation_placeholders={
                        "entities": self._describe(unknown_entities, unknown_active),
                        "helper": entry.title,
                        "edit": "/config/helpers",
                    },
                )

    def _describe(self, unknown: set[str], unknown_active: set[str]) -> str:
        """Describe the unknown entities, qualifying the disabled-only ones.

        An entity is only qualified when nothing that runs references it. A
        Jinja template inside a disabled step is still seen by the template
        extraction, so such a reference stays unqualified -- the report errs
        towards saying too much rather than calling a live problem harmless.
        """
        described = async_describe_unknown_entities(self.hass, sorted(unknown_active))
        if disabled_only := unknown - unknown_active:
            described = "\n".join(
                part
                for part in (
                    described,
                    async_describe_unknown_entities(
                        self.hass,
                        sorted(disabled_only),
                        note="only referenced from disabled steps",
                    ),
                )
                if part
            )
        return described
