"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components import script
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from . import AbstractSpookRepair
from ..const import LOGGER


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced devices in scripts."""

    domain = script.DOMAIN
    repair = "script_unknown_device_references"
    events = {dr.EVENT_DEVICE_REGISTRY_UPDATED}

    _entity_component: EntityComponent[script.ScriptEntity]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._entity_component = self.hass.data[DATA_INSTANCES][self.domain]
        await super().async_activate()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug(f"Spook is inspecting: {self.repair}")
        devices = {device.id for device in self.device_registry.devices.values()}
        for entity in self._entity_component.entities:
            if unknown_devices := entity.script.referenced_devices - devices:
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
                    f"Spook found unknown devices in {entity.entity_id} "
                    f"and created an issue for it; Devices: {unknown_devices}"
                )
            else:
                self.async_delete_issue(entity.entity_id)
