"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.config_entries import SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntry
from homeassistant.const import (
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_COMPONENT_LOADED,
)
from homeassistant.core import valid_entity_id
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ..const import LOGGER
from . import AbstractSpookRepair

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced entity in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_entity_references"
    events = {
        EVENT_COMPONENT_LOADED,
        automation.EVENT_AUTOMATION_RELOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        "event_counter_reloaded",
        "event_derivative_reloaded",
        "event_group_reloaded",
        "event_input_boolean_reloaded",
        "event_input_button_reloaded",
        "event_input_datetime_reloaded",
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

    _entity_component: EntityComponent[automation.AutomationEntity]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._entity_component = self.hass.data[DATA_INSTANCES][self.domain]
        await super().async_activate()

        # Listen for config entry changes, this might have an impact
        # on the available entities (those not in the entity registry)
        async def _async_update_listener(
            _hass: HomeAssistant,
            _entry: ConfigEntry,
        ) -> None:
            """Handle options update."""
            await self.inspect_debouncer.async_call()

        async_dispatcher_connect(
            self.hass,
            SIGNAL_CONFIG_ENTRY_CHANGED,
            _async_update_listener,
        )

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

        for entity in self._entity_component.entities:
            # Filter out scenes, groups & device_tracker entities.
            # Those can be created on the fly with services, which we
            # currently cannot detect yet. Let's prevent some false positives.
            if unknown_entities := {
                entity_id
                for entity_id in entity.referenced_entities
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
            }:
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "entities": "\n".join(
                            f"- `{entity_id}`" for entity_id in unknown_entities
                        ),
                        "automation": entity.name,
                        "edit": f"/config/automation/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown entities in %s "
                        "and created an issue for it; Entities: %s",
                    ),
                    entity.entity_id,
                    ", ".join(unknown_entities),
                )
            else:
                self.async_delete_issue(entity.entity_id)
