"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_STATE_CHANGED
from homeassistant.core import Event, callback
from homeassistant.helpers import entity_registry as er

from ....action_extraction import (
    async_extract_entities_from_helper_actions,
    extract_not_entity_ids_from_config,
)
from ....const import LOGGER
from ....entity_filtering import (
    async_filter_known_entity_ids,
    async_get_all_entity_ids,
    async_get_all_services,
    async_name_helper_in_the_registry,
)
from ....entity_suggestions import async_describe_unknown_entities
from ....reference_extraction import without_disabled_steps, without_never_rendered
from ....repairs import AbstractSpookRepair
from ....template_extraction import async_extract_entities_from_config
from ...automation.repairs.unknown_entity_references import (
    extract_entities_from_automation_config,
)
from ..configuration import (
    EVENT_TEMPLATE_RELOADED,
    YamlTemplateEntity,
    async_get_yaml_template_entities,
    async_is_current,
    own_configuration,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds unknown entities referenced in template entities.

    Template helper config entries store their templates in the entry
    options; a template referencing a removed entity resolves to
    ``unknown`` and is otherwise silent. Template entities from the
    `template:` section of the configuration are read from the entities
    themselves, and a trigger based one also from the triggers it waits
    for: a trigger on an entity that is gone never fires.
    """

    domain = "template"
    repair = "template_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_TEMPLATE_RELOADED,
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

            # Extracting the actions twice separates references that a step
            # carrying `enabled: false` is the only source of: those cannot
            # break a run, so the report says so instead of listing them
            # alongside the ones that can.
            active = referenced | await async_extract_entities_from_helper_actions(
                self.hass,
                options,
                include_disabled=False,
                known_services=known_services,
            )
            referenced |= await async_extract_entities_from_helper_actions(
                self.hass, options, known_services=known_services
            )

            await self._async_report(
                issue_id=entry.entry_id,
                config=options,
                referenced=referenced,
                active=active,
                known_entity_ids=known_entity_ids,
                translation_key=None,
                translation_placeholders={
                    "helper": entry.title,
                    "entity_id": async_name_helper_in_the_registry(
                        self.hass, entry.entry_id
                    ),
                    "edit": "/config/helpers",
                },
            )

        for template_entity in async_get_yaml_template_entities(self.hass):
            # Reading a configuration is CPU-bound, and there can be many
            # template entities: the event loop gets a turn after each.
            await asyncio.sleep(0)
            self.possible_issue_ids.add(template_entity.entity_id)

            config = template_entity.config
            # Read once as it is and once without its disabled steps, for the
            # same reason as above. Here the templates go too: a disabled
            # trigger or step is never rendered, whatever is in it.
            referenced = await self._async_named_in_yaml(config, known_services)
            active = await self._async_named_in_yaml(
                without_disabled_steps(config), known_services
            )

            await self._async_report(
                issue_id=template_entity.entity_id,
                config=config,
                referenced=referenced,
                active=active,
                known_entity_ids=known_entity_ids,
                # There is no editor for YAML, so the issue says where to look.
                translation_key=f"{self.repair}_yaml",
                translation_placeholders={
                    "name": template_entity.name,
                    "entity_id": template_entity.entity_id,
                },
                template_entity=template_entity,
            )

    async def _async_named_in_yaml(
        self, config: dict[str, Any], known_services: set[str]
    ) -> set[str]:
        """Return the entities a template entity from YAML names.

        Its templates, the actions of its own (like a switch's `turn_on`),
        and for a trigger based one the triggers, conditions and actions of
        its section, read the way an automation's are.
        """
        named = await async_extract_entities_from_config(
            self.hass, without_never_rendered(config), known_services
        )
        # Home Assistant validates every action of a template entity into a
        # list of steps. A mapping is something else, like its attributes,
        # where `entity_id` is a value it shows and not a target.
        actions = {
            key: value
            for key, value in own_configuration(config).items()
            if isinstance(value, list)
        }
        named |= await async_extract_entities_from_helper_actions(
            self.hass, actions, known_services=known_services
        )
        named |= await extract_entities_from_automation_config(
            self.hass, config, known_services
        )
        return named

    async def _async_report(  # noqa: PLR0913 # pylint: disable=too-many-arguments
        self,
        *,
        issue_id: str,
        config: dict[str, Any],
        referenced: set[str],
        active: set[str],
        known_entity_ids: set[str],
        translation_key: str | None,
        translation_placeholders: dict[str, str],
        template_entity: YamlTemplateEntity | None = None,
    ) -> None:
        """Raise an issue for what one template names that does not exist."""
        unknown_entities = async_filter_known_entity_ids(
            self.hass,
            referenced,
            known_entity_ids=known_entity_ids,
        )
        # Where an entity ID goes, something that is no entity ID at all
        # finds nothing, whatever exists. Listed with the rest, said apart.
        not_entity_ids = extract_not_entity_ids_from_config(self.hass, config)

        if not unknown_entities and not not_entity_ids:
            return

        unknown_active = async_filter_known_entity_ids(
            self.hass,
            active,
            known_entity_ids=known_entity_ids,
        )
        described = await self._async_describe(
            unknown_entities, unknown_active, not_entity_ids
        )

        # Reading and describing it took a while. A template entity reloaded
        # meanwhile may say something else entirely, and the reload starts
        # another round that looks at that.
        if template_entity is not None and not async_is_current(
            self.hass, template_entity
        ):
            return

        self.async_create_issue(
            issue_id=issue_id,
            # Carrying which of them nothing running references any more,
            # because the report says so and that changes when a step is
            # enabled. Left out, a dismissal made while a reference was
            # harmless would outlive it becoming a live problem, which is
            # the thing an ID of its own prevents.
            references=[
                *unknown_active,
                *(
                    f"{entity_id} (disabled)"
                    for entity_id in unknown_entities - unknown_active
                ),
                *not_entity_ids,
            ],
            translation_key=translation_key,
            translation_placeholders={
                "entities": described,
                **translation_placeholders,
            },
        )

    async def _async_describe(
        self, unknown: set[str], unknown_active: set[str], not_entity_ids: set[str]
    ) -> str:
        """Describe the unknown entities, qualifying the disabled-only ones.

        An entity is only qualified when nothing that runs references it. In
        a template helper, a Jinja template inside a disabled step is still
        seen by the template extraction, so such a reference stays
        unqualified: the report errs towards saying too much rather than
        calling a live problem harmless.

        What is no entity ID at all comes last, without a guess at what was
        meant: a wrong suggestion is worse than none.
        """
        described = await async_describe_unknown_entities(
            self.hass, sorted(unknown_active)
        )
        if disabled_only := unknown - unknown_active:
            described = "\n".join(
                part
                for part in (
                    described,
                    await async_describe_unknown_entities(
                        self.hass,
                        sorted(disabled_only),
                        note="only referenced from disabled steps",
                    ),
                )
                if part
            )
        return "\n".join(
            line
            for line in (
                described,
                *(
                    f"- `{value}` (not an entity ID)"
                    for value in sorted(not_entity_ids)
                ),
            )
            if line
        )
