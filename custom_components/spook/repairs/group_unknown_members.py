"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components import group
from homeassistant.const import (
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_COMPONENT_LOADED,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM, EntityPlatform

from ..const import LOGGER
from . import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown member entities in groups."""

    domain = group.DOMAIN
    repair = "group_unknown_members"
    events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        "event_group_reloaded",
        "event_input_boolean_reloaded",
        "event_input_button_reloaded",
        "event_input_number_reloaded",
        "event_input_select_reloaded",
        "event_input_text_reloaded",
        "event_integration_reloaded",
        "event_min_max_reloaded",
        "event_mqtt_reloaded",
        "event_scene_reloaded",
        "event_schedule_reloaded",
        "event_template_reloaded",
        "event_threshold_reloaded",
        "event_tod_reloaded",
        "event_utility_meter_reloaded",
    }

    _entity_platforms: list[EntityPlatform]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._entity_platforms = self.hass.data[DATA_ENTITY_PLATFORM][self.domain]
        await super().async_activate()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        # Two sources for entities. The entities in the entity registry,
        # and the entities currently in the state machine. They will have lots
        # of overlap, but not all entities are in the entity registry and
        # not all have to be in the state machine right now.
        # Furthermore, add `all` and `none` to the list of known entities,
        # as they are valid targets.
        entity_ids = (
            {entity.entity_id for entity in self.entity_registry.entities.values()}
            .union(self.hass.states.async_entity_ids())
            .union({ENTITY_MATCH_ALL, ENTITY_MATCH_NONE})
        )

        for platform in self._entity_platforms:
            # We don't want to check the old style group platform
            for entity in platform.entities.values():
                members = []
                if platform.domain == group.DOMAIN:
                    members = entity.tracking
                elif hasattr(entity, "_entity_ids"):
                    # pylint: disable-next=protected-access
                    members = entity._entity_ids  # noqa: SLF001
                elif hasattr(entity, "_entities"):
                    # pylint: disable-next=protected-access
                    members = entity._entities  # noqa: SLF001

                # Filter out scenes, groups & device_tracker entities.
                # Those can be created on the fly with services, which we
                # currently cannot detect yet. Let's prevent some false positives.
                if unknown_entities := {
                    entity_id
                    for entity_id in members
                    if (
                        not entity_id.startswith(
                            ("device_tracker.", "group.", "scene."),
                        )
                        and entity_id not in entity_ids
                    )
                }:
                    self.async_create_issue(
                        issue_id=entity.entity_id,
                        translation_placeholders={
                            "entities": "\n".join(
                                f"- `{entity_id}`" for entity_id in unknown_entities
                            ),
                            "group": entity.name,
                            "entity_id": entity.entity_id,
                        },
                    )
                    LOGGER.debug(
                        "Spook found unknown member entities in %s "
                        "and created an issue for it; Entities: %s",
                        entity.entity_id,
                        ", ".join(unknown_entities),
                    )
                else:
                    self.async_delete_issue(entity.entity_id)
