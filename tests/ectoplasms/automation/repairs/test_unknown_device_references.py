"""Tests for automation unknown device reference repairs."""
# ruff: noqa: SLF001
# pylint: disable=protected-access,too-few-public-methods

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.ectoplasms.automation.repairs.unknown_device_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry as dr
    import pytest


class MockAutomationEntity:
    """Mock automation entity."""

    def __init__(
        self,
        *,
        raw_config: dict[str, object],
        referenced_devices: Iterable[str],
    ) -> None:
        """Initialize the mock automation entity."""
        self.raw_config = raw_config
        self.referenced_devices = set(referenced_devices)


async def test_event_trigger_data_device_id_is_not_reported_unknown(
    hass: HomeAssistant,
) -> None:
    """Event trigger ``event_data.device_id`` values are not device references."""
    entity = MockAutomationEntity(
        raw_config={
            "trigger": {
                "trigger": "event",
                "event_type": "hcu_integration_event",
                "event_data": {"device_id": "3014F711A0001F20C98F2F47"},
            },
        },
        referenced_devices={"3014F711A0001F20C98F2F47"},
    )
    repair = SpookRepair(hass)
    repair._known_device_ids = set()

    assert await repair._async_compute_unknown_references(entity) == set()


async def test_event_trigger_data_device_id_in_plural_triggers_is_not_reported_unknown(
    hass: HomeAssistant,
) -> None:
    """Plural event triggers can contain device IDs that are not device references."""
    entity = MockAutomationEntity(
        raw_config={
            "triggers": [
                {
                    "trigger": "event",
                    "event_type": "hcu_integration_event",
                    "event_data": {"device_id": "3014F711A0001F20C98F2F47"},
                },
            ],
        },
        referenced_devices={"3014F711A0001F20C98F2F47"},
    )
    repair = SpookRepair(hass)
    repair._known_device_ids = set()

    assert await repair._async_compute_unknown_references(entity) == set()


async def test_pre_split_device_id_is_not_reported_unknown(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a device ID from before the Core 2026.8 device split is not unknown.

    A device that belonged to multiple config entries was split into one device
    per entry. Its original ID is gone from the registry, but Home Assistant
    still resolves it to the new devices, so the automation keeps working.
    """
    entry = MockConfigEntry(domain="test", title="Test")
    entry.add_to_hass(hass)
    split = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", "split-device")},
    )
    # Stubbed so this test also runs on cores that predate the device split.
    monkeypatch.setattr(
        device_registry.devices,
        "get_composite_splits",
        lambda: {"pre-split-id": [split]},
        raising=False,
    )

    entity = MockAutomationEntity(
        raw_config={
            "actions": [
                {
                    "action": "light.turn_on",
                    "target": {"device_id": "pre-split-id"},
                },
            ],
        },
        referenced_devices={"pre-split-id"},
    )
    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == set()
