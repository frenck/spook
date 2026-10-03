"""Tests for the spook.device_added trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import CoreState
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        area_registry as ar,
        device_registry as dr,
    )


async def _automation(hass: HomeAssistant) -> list[dict]:
    """Set up an automation on the trigger and record every run."""
    ran: list[dict] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(dict(call.data))

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "new device",
                    "trigger": {"platform": "spook.device_added"},
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "device_id": "{{ trigger.device_id }}",
                                "name": "{{ trigger.name }}",
                                "manufacturer": "{{ trigger.manufacturer }}",
                                "model": "{{ trigger.model }}",
                                "area_id": "{{ trigger.area_id }}",
                                "integrations": "{{ trigger.integrations }}",
                            },
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


def _plug(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, **kwargs: str
) -> dr.DeviceEntry:
    """Pair a plug, the way an integration registers one."""
    entry = MockConfigEntry(domain="zha", title="Zigbee")
    entry.add_to_hass(hass)
    return device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("zha", "00:11:22:33")},
        name="Plug",
        manufacturer="IKEA",
        model="TRETAKT",
        **kwargs,
    )


async def test_a_new_device_is_reported(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test a device added fires the trigger, with what it is and where."""
    kitchen = area_registry.async_create("Kitchen")
    ran = await _automation(hass)

    device = _plug(hass, device_registry, suggested_area="Kitchen")
    await hass.async_block_till_done()

    assert ran == [
        {
            "device_id": device.id,
            "name": "Plug",
            "manufacturer": "IKEA",
            "model": "TRETAKT",
            "area_id": kitchen.id,
            "integrations": ["zha"],
        }
    ]


async def test_a_device_changing_is_not_a_device_added(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test only a new device fires, not one that is renamed afterwards."""
    ran = await _automation(hass)
    device = _plug(hass, device_registry)
    await hass.async_block_till_done()

    device_registry.async_update_device(device.id, name_by_user="Coffee")
    await hass.async_block_till_done()

    assert len(ran) == 1


async def test_devices_registered_while_starting_stay_quiet(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test devices registered during a start are not news.

    Integrations register the devices they already had while Home Assistant
    starts, and that is not the house getting anything new.
    """
    ran = await _automation(hass)
    hass.set_state(CoreState.starting)

    _plug(hass, device_registry)
    await hass.async_block_till_done()

    assert ran == []
