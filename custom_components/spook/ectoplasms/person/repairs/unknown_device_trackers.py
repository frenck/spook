"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import person
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES

from ....const import LOGGER
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds device trackers a person points at that are gone.

    A person tracks a set of device trackers. When one is renamed or its
    integration is removed, the person keeps pointing at an entity that no
    longer exists. Device trackers can be state-only, so both the entity
    registry and the current states are checked before flagging one.
    """

    domain = person.DOMAIN
    repair = "person_unknown_device_trackers"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_on_reload = True
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        component: EntityComponent[person.Person] | None
        if not (component := self.hass.data.get(DATA_INSTANCES, {}).get(self.domain)):
            return  # Person is not set up; nothing to do.

        entity_registry = er.async_get(self.hass)
        for person_entity in component.entities:
            self.possible_issue_ids.add(person_entity.entity_id)

            unknown = [
                device_tracker
                for device_tracker in person_entity.device_trackers
                if entity_registry.async_get(device_tracker) is None
                and self.hass.states.get(device_tracker) is None
            ]
            if not unknown:
                continue

            self.async_create_issue(
                issue_id=person_entity.entity_id,
                is_fixable=True,
                data={
                    "person_entity_id": person_entity.entity_id,
                    "person": person_entity.name,
                    "device_trackers": async_describe_unknown_entities(
                        self.hass, sorted(unknown)
                    ),
                    "unknown_trackers": ",".join(sorted(unknown)),
                },
                translation_placeholders={"person": person_entity.name},
            )
            LOGGER.debug(
                "Spook found unknown device trackers for %s: %s",
                person_entity.entity_id,
                ", ".join(sorted(unknown)),
            )
