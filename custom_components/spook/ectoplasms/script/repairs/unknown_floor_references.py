"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import script
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_floor_ids, async_get_all_floor_ids


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced floors in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_floor_references"
    inspect_events = {fr.EVENT_FLOOR_REGISTRY_UPDATED}
    inspect_on_reload = True

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        if self.domain not in self.hass.data[DATA_INSTANCES]:
            return

        entity_component: EntityComponent[script.ScriptEntity] = self.hass.data[
            DATA_INSTANCES
        ][self.domain]

        known_floor_ids = async_get_all_floor_ids(self.hass)

        LOGGER.debug("Spook is inspecting: %s", self.repair)
        for entity in entity_component.entities:
            self.possible_issue_ids.add(entity.entity_id)
            if not isinstance(entity, script.UnavailableScriptEntity) and (
                unknown_floors := async_filter_known_floor_ids(
                    self.hass,
                    floor_ids=entity.script.referenced_floors,
                    known_floor_ids=known_floor_ids,
                )
            ):
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "floors": "\n".join(f"- `{floor}`" for floor in unknown_floors),
                        "script": entity.name,
                        "edit": f"/config/script/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown floors in %s "
                        "and created an issue for it; Floors: %s",
                    ),
                    entity.entity_id,
                    ", ".join(unknown_floors),
                )
