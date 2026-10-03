"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import CoreState, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import Trigger

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

_TRIGGER_SCHEMA = vol.Schema({vol.Optional(CONF_OPTIONS, default=dict): {}})


class SpookTrigger(Trigger):
    """Spook trigger that fires when a device is added.

    Home Assistant announces a new device on its bus and nowhere else, so a
    new plug paired by somebody else, or a Zigbee device that joined on its
    own, goes unnoticed until somebody browses the device list.
    """

    trigger = "device_added"

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,  # noqa: ARG003
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config."""
        return _TRIGGER_SCHEMA(config)  # type: ignore[no-any-return]

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        registry = dr.async_get(self._hass)

        @callback
        def device_registry_changed(
            event: Event[dr.EventDeviceRegistryUpdatedData],
        ) -> None:
            """Fire for a device that was just created.

            Only once Home Assistant is up. While it starts, integrations
            register the devices they already had, and one set up for the
            first time can bring dozens along, none of them new to the house.
            `is_running` is not the question: that is already true while
            starting, which is the half of a start this sits out.
            """
            if event.data["action"] != "create":
                return

            if self._hass.state is not CoreState.running:
                return

            if (device := registry.async_get(event.data["device_id"])) is None:
                return

            run_action(
                {
                    "device_id": device.id,
                    "name": device.name,
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "area_id": device.area_id,
                    "integrations": sorted(
                        entry.domain
                        for entry_id in device.config_entries
                        if (
                            entry := self._hass.config_entries.async_get_entry(entry_id)
                        )
                    ),
                },
                f"device {device.name} added",
                event.context,
            )

        return self._hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, device_registry_changed
        )
