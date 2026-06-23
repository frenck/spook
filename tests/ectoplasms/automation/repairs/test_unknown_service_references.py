"""Tests for automation unknown service reference repairs."""

# pylint: disable=protected-access

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.const import EVENT_COMPONENT_LOADED

from custom_components.spook.ectoplasms.automation.repairs.unknown_service_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def test_automation_unknown_service_repair_inspects_when_components_load() -> None:
    """Test automation service references are rechecked when components load."""
    assert EVENT_COMPONENT_LOADED in SpookRepair.inspect_events


def test_automation_unknown_service_repair_skips_disabled_automations(
    hass: HomeAssistant,
) -> None:
    """Test disabled automations are not inspected for unknown services."""
    repair = SpookRepair(hass)
    entity = SimpleNamespace(enabled=False)

    assert not repair._should_inspect_entity(entity)  # noqa: SLF001
