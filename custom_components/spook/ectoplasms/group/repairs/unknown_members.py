"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import group
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM, EntityPlatform

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_entity_ids, async_get_all_entity_ids


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown member entities in groups."""

    domain = group.DOMAIN
    repair = "group_unknown_members"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = group.DOMAIN
    inspect_on_reload = True

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass)

        platforms: list[EntityPlatform] | None
        if not (platforms := self.hass.data[DATA_ENTITY_PLATFORM].get(self.domain)):
            return  # Nothing to do.

        for platform in platforms:
            # We don't want to check the old style group platform
            for entity in platform.entities.values():
                self.possible_issue_ids.add(entity.entity_id)
                members = []
                if platform.domain == group.DOMAIN:
                    members = entity.tracking
                elif hasattr(entity, "_entity_ids"):
                    # pylint: disable-next=protected-access
                    members = entity._entity_ids  # noqa: SLF001
                elif hasattr(entity, "_entities"):
                    # pylint: disable-next=protected-access
                    members = entity._entities  # noqa: SLF001

                if unknown_entities := async_filter_known_entity_ids(
                    self.hass, entity_ids=members, known_entity_ids=known_entity_ids
                ):
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
