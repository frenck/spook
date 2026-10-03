"""Tests for the spook.device_added trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import Context, CoreState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import
from custom_components.spook.ectoplasms.spook.triggers.device_added import (
    SpookTrigger,
)

if TYPE_CHECKING:
    import pytest

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import area_registry as ar


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
                                "integration": "{{ trigger.integration }}",
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
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a device added fires the trigger, with what it is and where.

    Read without the deprecated `config_entries`, which warns on use.
    """
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
            "integration": "zha",
        }
    ]
    assert "config_entries" not in caplog.text


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


async def test_a_part_of_another_device_has_no_make_or_model(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a child device, one outlet of a power strip, is reported plainly.

    It has no make or model of its own. Home Assistant still answers when
    asked, with nothing and a deprecation warning, so the warning is what
    tells asking from not asking.
    """
    ran = await _automation(hass)
    strip = _plug(hass, device_registry)
    await hass.async_block_till_done()

    device_registry.async_get_or_create_child(
        config_entry_id=strip.config_entry_id,
        identifiers={("zha", "00:11:22:33-1")},
        name="Outlet 1",
        parent_device_id=strip.id,
    )
    await hass.async_block_till_done()

    assert ran[1]["name"] == "Outlet 1"
    assert ran[1]["manufacturer"] is None
    assert ran[1]["model"] is None
    assert ran[1]["integration"] == "zha"
    assert "ChildDeviceEntry" not in caplog.text


async def test_whoever_added_it_is_on_the_run(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the context of the registry change is handed to the automation.

    Spook's own context conditions read who did it off the trigger.
    """
    device = _plug(hass, device_registry)
    handed: list[Context | None] = []
    trigger = SpookTrigger(hass, TriggerConfig(key="device_added"))

    def _run(_payload, _description, context=None) -> None:  # noqa: ANN001
        handed.append(context)

    unsub = await trigger.async_attach_runner(_run)
    theirs = Context(user_id="abc123")
    hass.bus.async_fire(
        dr.EVENT_DEVICE_REGISTRY_UPDATED,
        {"action": "create", "device_id": device.id},
        context=theirs,
    )
    await hass.async_block_till_done()
    unsub()

    assert handed == [theirs]
