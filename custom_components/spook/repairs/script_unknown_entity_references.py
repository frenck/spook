"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components import script
from homeassistant.config_entries import SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntry
from homeassistant.const import (
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_COMPONENT_LOADED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from . import AbstractSpookRepair
from ..const import LOGGER


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced entity in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_entity_references"
    events = {
        EVENT_COMPONENT_LOADED,
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

    _entity_component: EntityComponent[script.ScriptEntity]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._entity_component = self.hass.data[DATA_INSTANCES][self.domain]
        await super().async_activate()

        # Listen for config entry changes, this might have an impact
        # on the available entities (those not in the entity registry)
        async def _async_update_listener(
            _hass: HomeAssistant, _entry: ConfigEntry
        ) -> None:
            """Handle options update."""
            await self.inspect_debouncer.async_call()

        async_dispatcher_connect(
            self.hass, SIGNAL_CONFIG_ENTRY_CHANGED, _async_update_listener
        )

        # Give all integration some time to startup

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug(f"Spook is inspecting: {self.repair}")
        # Two sources for entities. The entities in the entity registry,
        # and the entities currently in the state machine. They will have lots
        # of overlap, but not all entities are in the entity registry and
        # not all have to be in the state machine right now.
        entity_ids = {
            entity.entity_id for entity in self.entity_registry.entities.values()
        }.union(self.hass.states.async_entity_ids())

        for entity in self._entity_component.entities:
            # Get all referenced entities, remove the ones that are known
            # and remove match `all` and `none` as they are not real entities.
            referenced_entities = (
                entity.script.referenced_entities
                - entity_ids
                - {ENTITY_MATCH_NONE, ENTITY_MATCH_ALL}
            )

            # Filter out scenes, groups & device_tracker entities.
            # Those can be created on the fly with services, which we
            # currently cannot detect yet. Let's prevent some false positives.
            referenced_entities = {
                entity_id
                for entity_id in referenced_entities
                if (
                    not entity_id.startswith("device_tracker.")
                    and not entity_id.startswith("group.")
                    and not entity_id.startswith("scene.")
                )
            }

            if unknown_entities := referenced_entities - entity_ids:
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
                LOGGER.debug(
                    f"Spook found unknown entities in {entity.entity_id} "
                    f"and created an issue for it; Entities: {unknown_entities}"
                )
            else:
                self.async_delete_issue(entity.entity_id)
