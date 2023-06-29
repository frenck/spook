"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components import sensor
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM, EntityPlatform

from ....const import LOGGER
from ....repairs import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown source entites for integration."""

    domain = "integration"
    repair = "integration_unknown_source"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        "event_integration_reloaded",
    }

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        platforms: list[EntityPlatform] | None
        if not (platforms := self.hass.data[DATA_ENTITY_PLATFORM].get(self.domain)):
            return  # Nothing to do.

        entity_ids = {
            entity.entity_id for entity in self.entity_registry.entities.values()
        }.union(self.hass.states.async_entity_ids())

        for platform in platforms:
            # We only care about the sensor domain
            if platform.domain != sensor.DOMAIN:
                continue

            for entity in platform.entities.values():
                # pylint: disable-next=protected-access
                source = entity._sensor_source_id  # noqa: SLF001
                if source not in entity_ids:
                    self.async_create_issue(
                        issue_id=entity.entity_id,
                        translation_placeholders={
                            "entity_id": entity.entity_id,
                            "helper": entity.name,
                            "source": source,
                        },
                    )
                    LOGGER.debug(
                        "Spook found unknown source entity %s in %s "
                        "and created an issue for it",
                        source,
                        entity.entity_id,
                    )
                else:
                    self.async_delete_issue(entity.entity_id)
