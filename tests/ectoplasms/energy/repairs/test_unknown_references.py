"""Tests for the energy dashboard unknown references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.energy.validate import (
    EnergyPreferencesValidation,
    ValidationIssues,
)

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.energy.repairs import unknown_references
from custom_components.spook.ectoplasms.energy.repairs.unknown_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir
    import pytest

_ISSUE_ID = "energy_unknown_references_energy_unknown_references"


def _install_validation(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    result: EnergyPreferencesValidation,
) -> None:
    """Make the repair see the given validation result with energy loaded."""
    hass.config.components.add("energy")

    async def _async_validate(_hass: HomeAssistant) -> EnergyPreferencesValidation:
        return result

    monkeypatch.setattr(unknown_references, "async_validate", _async_validate)


async def test_missing_energy_entity_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an energy source referencing a removed entity is reported."""
    result = EnergyPreferencesValidation()
    source_issues = ValidationIssues()
    source_issues.add_issue(hass, "entity_not_defined", "sensor.ghost_meter")
    # A transient issue type must not be reported.
    source_issues.add_issue(hass, "entity_unavailable", "sensor.flaky")
    result.energy_sources.append(source_issues)

    _install_validation(hass, monkeypatch, result)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    assert "sensor.ghost_meter" in issue.translation_placeholders["entities"]
    assert "sensor.flaky" not in issue.translation_placeholders["entities"]


async def test_only_transient_issues_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test transient validation issues alone produce no repair issue."""
    result = EnergyPreferencesValidation()
    device_issues = ValidationIssues()
    device_issues.add_issue(hass, "entity_unavailable", "sensor.flaky")
    result.device_consumption.append(device_issues)

    _install_validation(hass, monkeypatch, result)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_energy_not_set_up_is_a_no_op(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair does nothing when the energy dashboard is absent."""
    # A fresh test instance has no energy component set up.
    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None
