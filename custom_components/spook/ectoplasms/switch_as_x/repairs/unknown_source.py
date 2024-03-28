"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM, EntityPlatform

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_get_all_entity_ids


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown source entites for switch_as_x."""

    domain = "switch_as_x"
    repair = "switch_as_x_unknown_source"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = "switch_as_x"

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        platforms: list[EntityPlatform] | None
        if not (platforms := self.hass.data[DATA_ENTITY_PLATFORM].get(self.domain)):
            return  # Nothing to do, switch_as_x is not loaded

        known_entity_ids = async_get_all_entity_ids(self.hass)

        for platform in platforms:
            for entity in platform.entities.values():
                self.possible_issue_ids.add(entity.entity_id)
                # pylint: disable-next=protected-access
                source = entity._switch_entity_id  # noqa: SLF001
                if source not in known_entity_ids:
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
