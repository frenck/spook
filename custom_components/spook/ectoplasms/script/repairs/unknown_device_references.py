"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import script
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_device_ids, async_get_all_device_ids


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced devices in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_device_references"
    inspect_events = {dr.EVENT_DEVICE_REGISTRY_UPDATED}
    inspect_config_entry_changed = True
    inspect_on_reload = True

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        if self.domain not in self.hass.data[DATA_INSTANCES]:
            return

        entity_component: EntityComponent[script.ScriptEntity] = self.hass.data[
            DATA_INSTANCES
        ][self.domain]

        known_device_ids = async_get_all_device_ids(self.hass)

        LOGGER.debug("Spook is inspecting: %s", self.repair)
        for entity in entity_component.entities:
            self.possible_issue_ids.add(entity.entity_id)
            if not isinstance(entity, script.UnavailableScriptEntity) and (
                unknown_devices := async_filter_known_device_ids(
                    self.hass,
                    device_ids=entity.script.referenced_devices,
                    known_device_ids=known_device_ids,
                )
            ):
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    translation_placeholders={
                        "devices": "\n".join(
                            f"- `{device}`" for device in unknown_devices
                        ),
                        "script": entity.name,
                        "edit": f"/config/script/edit/{entity.unique_id}",
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown devices in %s "
                        "and created an issue for it; Devices: %s",
                    ),
                    entity.entity_id,
                    ", ".join(unknown_devices),
                )
