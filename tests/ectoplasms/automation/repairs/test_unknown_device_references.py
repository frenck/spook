"""Tests for automation unknown device reference repairs."""
# ruff: noqa: SLF001
# pylint: disable=protected-access,too-few-public-methods

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.spook.ectoplasms.automation.repairs.unknown_device_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant


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
