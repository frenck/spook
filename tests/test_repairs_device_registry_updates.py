"""Tests for which device registry updates have a repair look again."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.helpers import device_registry as dr

from custom_components.spook.repairs import (
    AbstractSpookRepair,
    DeviceReferencesRepairMixin,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

# Plenty to tell a filtered stream from one that only got debounced together.
UNRELATED_DEVICES = 25


class _EveryDeviceRepair(AbstractSpookRepair):
    """Repair that looks again on every device registry update."""

    domain = "mock"
    repair = "mock_every_device"
    inspect_events = {dr.EVENT_DEVICE_REGISTRY_UPDATED}

    inspections = 0

    async def async_inspect(self) -> None:
        """Count the inspection."""
        self.inspections += 1


class _OneDeviceRepair(_EveryDeviceRepair):
    """Repair whose rounds find one device ID named."""

    repair = "mock_named_device"
    named: str = "0" * 32

    async def async_inspect(self) -> None:
        """Count the inspection and collect the named device ID."""
        await super().async_inspect()
        self._remember_referenced_device_ids({self.named})

    def _remember_referenced_device_ids(self, device_ids: set[str]) -> None:
        """Have the mixin provide this."""
        raise NotImplementedError


class _NamedDeviceRepair(DeviceReferencesRepairMixin, _OneDeviceRepair):
    """Repair that only looks again for the device it names."""


async def _settle(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the inspection debouncer run whatever it has waiting."""
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _add_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, count: int
) -> list[dr.DeviceEntry]:
    """Add ``count`` devices nothing names, the way discovery does."""
    entry = MockConfigEntry(domain="test", title="Test")
    entry.add_to_hass(hass)
    return [
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("test", f"discovered-{index}")},
        )
        for index in range(count)
    ]


async def test_devices_nothing_names_are_let_go(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Devices that come and go unnamed cost no round at all."""
    repair = _NamedDeviceRepair(hass)
    await repair.async_activate()
    await _settle(hass, freezer)
    assert repair.inspections == 1

    for device in _add_devices(hass, device_registry, UNRELATED_DEVICES):
        await _settle(hass, freezer)
        device_registry.async_update_device(device.id, name="Renamed")
        await _settle(hass, freezer)
        device_registry.async_remove_device(device.id)
        await _settle(hass, freezer)

    assert repair.inspections == 1
    await repair.async_deactivate()


async def test_named_device_going_has_a_look(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A device that is named going away makes its reference unknown."""
    (device,) = _add_devices(hass, device_registry, 1)
    repair = _NamedDeviceRepair(hass)
    repair.named = device.id
    await repair.async_activate()
    await _settle(hass, freezer)
    assert repair.inspections == 1

    device_registry.async_remove_device(device.id)
    await _settle(hass, freezer)

    assert repair.inspections == 2  # noqa: PLR2004
    await repair.async_deactivate()


async def test_other_repairs_still_look_at_every_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A repair that says nothing about devices keeps looking at all of them."""
    repair = _EveryDeviceRepair(hass)
    await repair.async_activate()
    await _settle(hass, freezer)
    assert repair.inspections == 1

    _add_devices(hass, device_registry, 1)
    await _settle(hass, freezer)

    assert repair.inspections == 2  # noqa: PLR2004
    await repair.async_deactivate()
