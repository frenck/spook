"""Tests for automation unknown service reference repairs."""

from __future__ import annotations

from homeassistant.const import EVENT_COMPONENT_LOADED

from custom_components.spook.ectoplasms.automation.repairs.unknown_service_references import (
    SpookRepair,
)


def test_automation_unknown_service_repair_inspects_when_components_load() -> None:
    """Test automation service references are rechecked when components load."""
    assert EVENT_COMPONENT_LOADED in SpookRepair.inspect_events
