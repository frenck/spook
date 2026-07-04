"""Tests for the empty areas repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.data_entry_flow import FlowResultType

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs import empty_areas
from custom_components.spook.ectoplasms.homeassistant.repairs.empty_areas import (
    SpookRepair,
)
from custom_components.spook.repairs import EmptyAreaFixFlow, async_create_fix_flow

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        area_registry as ar,
        device_registry as dr,
        entity_registry as er,
        issue_registry as ir,
    )
    import pytest

# Comfortably past the creation grace period.
_AGED = timedelta(days=2)


def _issue_id(area_id: str) -> str:
    """Return the registry issue id for an area."""
    return f"empty_areas_{area_id}"


async def test_empty_area_is_reported(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an aged area with nothing in it and no references is reported."""
    area = area_registry.async_create("Ghost Room")
    freezer.tick(_AGED)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(area.id))
    assert issue
    assert issue.is_fixable
    assert issue.translation_placeholders == {"area": "Ghost Room"}
    assert issue.data == {"empty_area_id": area.id, "area": "Ghost Room"}


async def test_recently_created_area_is_not_reported(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a just-created area is left alone during its grace period."""
    area = area_registry.async_create("Brand New")

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(area.id)) is None


async def test_area_with_entity_is_not_reported(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an area that holds an entity is left alone."""
    area = area_registry.async_create("Living Room")
    entry = entity_registry.async_get_or_create("light", "hue", "ceiling")
    entity_registry.async_update_entity(entry.entity_id, area_id=area.id)
    freezer.tick(_AGED)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(area.id)) is None


async def test_area_with_device_is_not_reported(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an area that holds a device is left alone."""
    area = area_registry.async_create("Kitchen")
    entry = MockConfigEntry(domain="derivative")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("hue", "bridge")},
    )
    device_registry.async_update_device(device.id, area_id=area.id)
    freezer.tick(_AGED)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(area.id)) is None


async def test_area_referenced_by_automation_is_not_reported(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an empty area targeted by an automation is left alone."""
    area = area_registry.async_create("Hallway")
    freezer.tick(_AGED)
    monkeypatch.setattr(
        empty_areas,
        "automations_with_area",
        lambda _hass, area_id: ["automation.lights"] if area_id == area.id else [],
    )

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(area.id)) is None


def _flow_for(hass: HomeAssistant, area_id: str, area_name: str) -> EmptyAreaFixFlow:
    """Build an empty-area fix flow as the framework would wire it up."""
    flow = EmptyAreaFixFlow()
    flow.hass = hass
    flow.issue_id = _issue_id(area_id)
    flow.data = {"empty_area_id": area_id, "area": area_name}
    return flow


async def test_fix_flow_remove_option_removes_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test the remove menu option deletes the area."""
    area = area_registry.async_create("Ghost Room")

    flow = await async_create_fix_flow(
        hass,
        _issue_id(area.id),
        {"empty_area_id": area.id, "area": "Ghost Room"},
    )
    assert isinstance(flow, EmptyAreaFixFlow)
    flow.hass = hass
    flow.data = {"empty_area_id": area.id, "area": "Ghost Room"}

    # The menu is shown first, area still present.
    menu = await flow.async_step_init()
    assert menu["type"] == FlowResultType.MENU
    assert area_registry.async_get_area(area.id) is not None

    # Choosing remove deletes the area.
    result = await flow.async_step_remove()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert area_registry.async_get_area(area.id) is None


async def test_fix_flow_ignore_option_dismisses_issue(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the keep menu option ignores the issue and keeps the area."""
    area = area_registry.async_create("Hallway")
    freezer.tick(_AGED)
    await SpookRepair(hass).async_inspect()
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(area.id))

    flow = _flow_for(hass, area.id, "Hallway")
    result = await flow.async_step_ignore()

    assert result["type"] == FlowResultType.ABORT
    # Area stays, issue stays but is now ignored.
    assert area_registry.async_get_area(area.id) is not None
    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(area.id))
    assert issue is not None
    assert issue.dismissed_version is not None


async def test_fix_flow_remove_survives_already_removed_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test removing an area that is already gone does not blow up."""
    flow = _flow_for(hass, "gone", "Gone")

    result = await flow.async_step_remove()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert area_registry.async_get_area("gone") is None
