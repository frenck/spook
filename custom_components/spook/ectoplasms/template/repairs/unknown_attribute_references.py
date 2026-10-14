"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.template.const import CONF_ATTRIBUTES
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....attribute_checking import (
    NAMES_THE_STATE_HINT,
    UnknownAttribute,
    async_unknown_attributes,
    names_the_state,
)
from ....const import LOGGER
from ....entity_filtering import async_name_helper_in_the_registry
from ....reference_extraction import (
    NamedReferences,
    extract_attribute_references_from_config,
)
from ....repairs import AbstractSpookRepair
from ...spook.triggers.state_changed import async_watched_entity_ids
from ..configuration import (
    EVENT_TEMPLATE_RELOADED,
    YamlTemplateEntity,
    async_get_yaml_template_entities,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _reference(entity_id: str, attribute: str) -> str:
    """Return how an unknown attribute is written down in an issue.

    The same way the automation and script repairs write it down.
    """
    return f"{entity_id}:{attribute}"


def _finding_line(finding: UnknownAttribute) -> str:
    """Return how one unknown attribute reads in the issue."""
    line = f"- `{finding.attribute}` of `{finding.entity_id}`"
    if finding.suggestion is not None:
        line += f" (did you mean `{finding.suggestion}`?)"
    elif names_the_state(finding.entity_id, finding.attribute):
        line += f" ({NAMES_THE_STATE_HINT})"
    return line


def _references_in_template_entity(config: dict[str, Any]) -> NamedReferences:
    """Return what the configuration of a template entity names.

    The attributes it gives its entity are named by whoever writes them. An
    attribute called `condition` next to ones called `entity_id` and
    `attribute` is not a condition, so only their templates are read.
    """
    config = dict(config)
    attributes = config.pop(CONF_ATTRIBUTES, None)
    if isinstance(attributes, dict):
        attributes = list(attributes.values())
    return extract_attribute_references_from_config([config, attributes])


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds unknown attributes used in template entities.

    A template helper made in the UI keeps its templates and actions in the
    options of its config entry. A template entity from the `template:`
    section of the configuration keeps them on the entity, and a trigger
    based one also has the triggers, conditions and actions of its section.
    A template reading an attribute its entity never has gets nothing, and a
    trigger or condition waiting on one never fires or passes. None of them
    says so.

    What an entity has is only known at runtime, and the last place to look
    is the recorder. So, like the automation and script repairs: not right at
    the start, when the recorder has its hands full, and once a day for what
    changes with time alone. The whole round goes to the recorder in one go.
    """

    domain = "template"
    repair = "template_unknown_attribute_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_TEMPLATE_RELOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = "template"
    inspect_on_entity_added_or_removed = True
    automatically_clean_up_issues = True
    first_inspection_delay = timedelta(minutes=10)
    inspect_interval = timedelta(days=1)

    _named: dict[str, tuple[Mapping[str, Any], NamedReferences]]
    _named_in_yaml: dict[str, tuple[YamlTemplateEntity, NamedReferences]]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self._named = {}
        self._named_in_yaml = {}

    def _references_in(self, entry: ConfigEntry) -> NamedReferences:
        """Return what the options of a helper name, and of which entities.

        Read once per set of options, remembered against the options
        themselves: changing a helper hands its entry new ones.
        """
        options = entry.options
        named = self._named.get(entry.entry_id)
        if named is None or named[0] is not options:
            named = (options, extract_attribute_references_from_config(dict(options)))
        self._named[entry.entry_id] = named
        return named[1]

    def _references_in_yaml(
        self, template_entity: YamlTemplateEntity
    ) -> NamedReferences:
        """Return what a template entity from YAML names, and of which entities.

        Read once per configuration, remembered against what it was read
        from: a reload hands every template entity a new one.
        """
        named = self._named_in_yaml.get(template_entity.entity_id)
        if named is None or not named[0].is_read_from(template_entity):
            named = (
                template_entity,
                _references_in_template_entity(template_entity.config),
            )
        self._named_in_yaml[template_entity.entity_id] = named
        return named[1]

    def _pairs_in(self, references: NamedReferences) -> set[tuple[str, str]]:
        """Return the (entity ID, attribute) pairs a configuration names.

        Resolved every round rather than remembered: what a registry ID stands
        for moves when the entity is renamed, and so does what Spook's own
        trigger in a wait for a trigger watches.
        """
        pairs = {
            (entity_id, attribute)
            for reference, attribute in references.pairs
            if (
                entity_id := er.async_resolve_entity_id(self.entity_registry, reference)
            )
        }
        for trigger_config, attribute in references.followed:
            pairs.update(
                (entity_id, attribute)
                for entity_id in async_watched_entity_ids(self.hass, trigger_config)
            )
        return pairs

    async def async_inspect(self) -> None:
        """Trigger an inspection.

        Nothing goes into ``possible_issue_ids``: an issue is keyed to its
        findings, and what this repair left behind is read back out of the
        registry instead.
        """
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        entries = self.hass.config_entries.async_entries(self.domain)

        named: dict[str, tuple[ConfigEntry, Mapping[str, Any], set[tuple[str, str]]]]
        named = {}
        for entry in entries:
            # Reading the options is CPU-bound, and a helper with actions can
            # be big: the event loop gets a turn after each.
            await asyncio.sleep(0)
            named[entry.entry_id] = (
                entry,
                entry.options,
                self._pairs_in(self._references_in(entry)),
            )

        named_in_yaml: dict[str, tuple[YamlTemplateEntity, set[tuple[str, str]]]]
        named_in_yaml = {}
        for template_entity in async_get_yaml_template_entities(self.hass):
            await asyncio.sleep(0)
            named_in_yaml[template_entity.entity_id] = (
                template_entity,
                self._pairs_in(self._references_in_yaml(template_entity)),
            )

        # Whatever is gone is forgotten.
        self._named = {
            entry_id: remembered
            for entry_id, remembered in self._named.items()
            if entry_id in named
        }
        self._named_in_yaml = {
            entity_id: remembered
            for entity_id, remembered in self._named_in_yaml.items()
            if entity_id in named_in_yaml
        }

        unknown = await async_unknown_attributes(
            self.hass,
            {
                pair
                for pairs in (
                    *(pairs for _, _, pairs in named.values()),
                    *(pairs for _, pairs in named_in_yaml.values()),
                )
                for pair in pairs
            },
        )
        by_pair = {
            (finding.entity_id, finding.attribute): finding for finding in unknown
        }

        for entry, options, pairs in named.values():
            # The recorder was asked in between. A helper removed or changed
            # meanwhile may say something else entirely, and changing it
            # starts another round that looks at that.
            if (
                self.hass.config_entries.async_get_entry(entry.entry_id) is not entry
                or entry.options is not options
            ):
                continue

            if not (findings := _findings(pairs, by_pair)):
                continue

            self.async_create_issue(
                issue_id=entry.entry_id,
                references=[
                    _reference(finding.entity_id, finding.attribute)
                    for finding in findings
                ],
                translation_placeholders={
                    "attributes": "\n".join(map(_finding_line, findings)),
                    "helper": entry.title,
                    "entity_id": async_name_helper_in_the_registry(
                        self.hass, entry.entry_id
                    ),
                    "edit": "/config/helpers",
                },
            )

        # The same goes for a template entity reloaded meanwhile.
        current = {
            template_entity.entity_id: template_entity
            for template_entity in async_get_yaml_template_entities(self.hass)
        }
        for template_entity, pairs in named_in_yaml.values():
            if (
                now := current.get(template_entity.entity_id)
            ) is None or not now.is_read_from(template_entity):
                continue

            if not (findings := _findings(pairs, by_pair)):
                continue

            self.async_create_issue(
                issue_id=template_entity.entity_id,
                references=[
                    _reference(finding.entity_id, finding.attribute)
                    for finding in findings
                ],
                # There is no editor for YAML, so the issue says where to look.
                translation_key=f"{self.repair}_yaml",
                translation_placeholders={
                    "attributes": "\n".join(map(_finding_line, findings)),
                    "name": template_entity.name,
                    "entity_id": template_entity.entity_id,
                },
            )


def _findings(
    pairs: set[tuple[str, str]], by_pair: dict[tuple[str, str], UnknownAttribute]
) -> list[UnknownAttribute]:
    """Return what of the pairs one template names is unknown, in order."""
    return sorted(
        (by_pair[pair] for pair in pairs & by_pair.keys()),
        key=lambda finding: (finding.entity_id, finding.attribute),
    )
