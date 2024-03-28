"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import script
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_area_ids, async_get_all_area_ids


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced areas in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_area_references"
    inspect_events = {ar.EVENT_AREA_REGISTRY_UPDATED}
    inspect_on_reload = True

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        if self.domain not in self.hass.data[DATA_INSTANCES]:
            return

        entity_component: EntityComponent[script.ScriptEntity] = self.hass.data[
            DATA_INSTANCES
        ][self.domain]

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_area_ids = async_get_all_area_ids(self.hass)

        for entity in entity_component.entities:
            self.possible_issue_ids.add(entity.entity_id)
            if not isinstance(entity, script.UnavailableScriptEntity) and (
                unknown_areas := async_filter_known_area_ids(
                    self.hass,
                    area_ids=entity.script.referenced_areas,
                    known_area_ids=known_area_ids,
                )
            ):
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "areas": "\n".join(f"- `{area}`" for area in unknown_areas),
                        "script": entity.name,
                        "edit": f"/config/script/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown areas in %s "
                        "and created an issue for it; Areas: %s"
                    ),
                    entity.entity_id,
                    ", ".join(unknown_areas),
                )
