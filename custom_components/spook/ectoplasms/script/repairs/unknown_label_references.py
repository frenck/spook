"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import script
from homeassistant.helpers import label_registry as lr
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_label_ids, async_get_all_label_ids


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced labels in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_label_references"
    inspect_events = {lr.EVENT_LABEL_REGISTRY_UPDATED}
    inspect_on_reload = True

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        if self.domain not in self.hass.data[DATA_INSTANCES]:
            return

        entity_component: EntityComponent[script.ScriptEntity] = self.hass.data[
            DATA_INSTANCES
        ][self.domain]

        known_label_ids = async_get_all_label_ids(self.hass)

        LOGGER.debug("Spook is inspecting: %s", self.repair)
        for entity in entity_component.entities:
            self.possible_issue_ids.add(entity.entity_id)
            if not isinstance(entity, script.UnavailableScriptEntity) and (
                unknown_labels := async_filter_known_label_ids(
                    self.hass,
                    label_ids=entity.script.referenced_labels,
                    known_label_ids=known_label_ids,
                )
            ):
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "labels": "\n".join(f"- `{label}`" for label in unknown_labels),
                        "script": entity.name,
                        "edit": f"/config/script/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown labels in %s "
                        "and created an issue for it; Labels: %s",
                    ),
                    entity.entity_id,
                    ", ".join(unknown_labels),
                )
