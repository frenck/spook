"""Tests for the empty floors repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import area_registry as ar, floor_registry as fr

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs import empty_floors
from custom_components.spook.ectoplasms.homeassistant.repairs.empty_floors import (
    SpookRepair,
)
from custom_components.spook.repairs import EmptyFloorFixFlow, async_create_fix_flow

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir
    import pytest

# Comfortably past the creation grace period.
_AGED = timedelta(days=2)


def _issue_id(floor_id: str) -> str:
    """Return the registry issue id for a floor."""
    return f"empty_floors_{floor_id}"


def _flow_for(hass: HomeAssistant, floor_id: str, floor_name: str) -> EmptyFloorFixFlow:
    """Build an empty-floor fix flow as the framework would wire it up."""
    flow = EmptyFloorFixFlow()
    flow.hass = hass
    flow.issue_id = _issue_id(floor_id)
    flow.data = {"empty_floor_id": floor_id, "floor": floor_name}
    return flow


async def test_empty_floor_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an aged floor with no areas and no references is reported."""
    floor = fr.async_get(hass).async_create("Attic")
    freezer.tick(_AGED)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(floor.floor_id))
    assert issue
    assert issue.is_fixable
    assert issue.translation_placeholders == {"floor": "Attic"}
    assert issue.data == {"empty_floor_id": floor.floor_id, "floor": "Attic"}


async def test_recently_created_floor_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a just-created floor is left alone during its grace period."""
    floor = fr.async_get(hass).async_create("Brand New")

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(floor.floor_id)) is None


async def test_floor_with_area_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a floor that holds an area is left alone."""
    floor = fr.async_get(hass).async_create("Ground")
    area = ar.async_get(hass).async_create("Kitchen")
    ar.async_get(hass).async_update(area.id, floor_id=floor.floor_id)
    freezer.tick(_AGED)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(floor.floor_id)) is None


async def test_floor_referenced_by_automation_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an empty floor targeted by an automation is left alone."""
    floor = fr.async_get(hass).async_create("First")
    freezer.tick(_AGED)
    monkeypatch.setattr(
        empty_floors,
        "automations_with_floor",
        lambda _hass, fid: ["automation.lights"] if fid == floor.floor_id else [],
    )

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(floor.floor_id)) is None


async def test_fix_flow_remove_option_removes_floor(
    hass: HomeAssistant,
) -> None:
    """Test the remove menu option deletes the floor."""
    floor = fr.async_get(hass).async_create("Attic")

    flow = await async_create_fix_flow(
        hass,
        _issue_id(floor.floor_id),
        {"empty_floor_id": floor.floor_id, "floor": "Attic"},
    )
    assert isinstance(flow, EmptyFloorFixFlow)
    flow.hass = hass
    flow.data = {"empty_floor_id": floor.floor_id, "floor": "Attic"}

    menu = await flow.async_step_init()
    assert menu["type"] == FlowResultType.MENU
    assert fr.async_get(hass).async_get_floor(floor.floor_id) is not None

    result = await flow.async_step_remove()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert fr.async_get(hass).async_get_floor(floor.floor_id) is None


async def test_fix_flow_ignore_option_dismisses_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the keep menu option ignores the issue and keeps the floor."""
    floor = fr.async_get(hass).async_create("First")
    freezer.tick(_AGED)
    await SpookRepair(hass).async_inspect()
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(floor.floor_id))

    flow = _flow_for(hass, floor.floor_id, "First")
    result = await flow.async_step_ignore()

    assert result["type"] == FlowResultType.ABORT
    assert fr.async_get(hass).async_get_floor(floor.floor_id) is not None
    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(floor.floor_id))
    assert issue is not None
    assert issue.dismissed_version is not None
