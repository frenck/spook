"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components import script
from homeassistant.const import (
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_COMPONENT_LOADED,
)
from homeassistant.core import valid_entity_id
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced entity in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True

    _issues: set[str] = set()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        if self.domain not in self.hass.data[DATA_INSTANCES]:
            return

        entity_component: EntityComponent[script.ScriptEntity] = self.hass.data[
            DATA_INSTANCES
        ][self.domain]

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        # Two sources for entities. The entities in the entity registry,
        # and the entities currently in the state machine. They will have lots
        # of overlap, but not all entities are in the entity registry and
        # not all have to be in the state machine right now.
        # Furthermore, add `all` and `none` to the list of known entities,
        # as they are valid targets.
        entity_ids = {
            entity.entity_id for entity in self.entity_registry.entities.values()
        }.union(self.hass.states.async_entity_ids()).union(
            {ENTITY_MATCH_ALL, ENTITY_MATCH_NONE}
        )

        possible_issue_ids: set[str] = set()
        for entity in entity_component.entities:
            possible_issue_ids.add(entity.entity_id)
            # Filter out scenes, groups & device_tracker entities.
            # Those can be created on the fly with services, which we
            # currently cannot detect yet. Let's prevent some false positives.
            if not isinstance(entity, script.UnavailableScriptEntity) and (
                unknown_entities := {
                    entity_id
                    for entity_id in entity.script.referenced_entities
                    if (
                        isinstance(entity_id, str)
                        and not entity_id.startswith(
                            (
                                "device_tracker.",
                                "group.",
                                "persistent_notification.",
                                "scene.",
                            ),
                        )
                        and entity_id not in entity_ids
                        and valid_entity_id(entity_id)
                    )
                }
            ):
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "entities": "\n".join(
                            f"- `{entity_id}`" for entity_id in unknown_entities
                        ),
                        "script": entity.name,
                        "edit": f"/config/script/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                self._issues.add(entity.entity_id)
                LOGGER.debug(
                    (
                        "Spook found unknown entities in %s and created an issue "
                        "for it; Entities: %s",
                    ),
                    entity.entity_id,
                    ", ".join(unknown_entities),
                )
            else:
                self.async_delete_issue(entity.entity_id)
                self._issues.discard(entity.entity_id)

        # Remove issues that are no longer valid
        for issue_id in self._issues - possible_issue_ids:
            self.async_delete_issue(issue_id)
            self._issues.discard(issue_id)
