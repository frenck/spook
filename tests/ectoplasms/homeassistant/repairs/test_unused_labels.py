"""Tests for the unused labels repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    label_registry as lr,
)

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs import unused_labels
from custom_components.spook.ectoplasms.homeassistant.repairs.unused_labels import (
    SpookRepair,
)
from custom_components.spook.repairs import UnusedLabelFixFlow, async_create_fix_flow

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir
    import pytest

# Comfortably past the creation grace period.
_AGED = timedelta(days=2)


def _issue_id(label_id: str) -> str:
    """Return the registry issue id for a label."""
    return f"unused_labels_{label_id}"


def _flow_for(
    hass: HomeAssistant, label_id: str, label_name: str
) -> UnusedLabelFixFlow:
    """Build an unused-label fix flow as the framework would wire it up."""
    flow = UnusedLabelFixFlow()
    flow.hass = hass
    flow.issue_id = _issue_id(label_id)
    flow.data = {"unused_label_id": label_id, "label": label_name}
    return flow


async def test_unused_label_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an aged label applied to nothing is reported."""
    label = lr.async_get(hass).async_create("Holiday")
    freezer.tick(_AGED)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(label.label_id))
    assert issue
    assert issue.is_fixable
    assert issue.translation_placeholders == {"label": "Holiday"}
    assert issue.data == {"unused_label_id": label.label_id, "label": "Holiday"}


async def test_recently_created_label_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a just-created label is left alone during its grace period."""
    label = lr.async_get(hass).async_create("Brand New")

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(label.label_id)) is None


async def test_label_on_entity_is_not_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a label applied to an entity is left alone."""
    label = lr.async_get(hass).async_create("Tagged")
    entry = entity_registry.async_get_or_create("light", "hue", "ceiling")
    entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})
    freezer.tick(_AGED)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(label.label_id)) is None


async def test_label_on_area_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a label applied to an area is left alone."""
    label = lr.async_get(hass).async_create("Zone")
    area = ar.async_get(hass).async_create("Kitchen")
    ar.async_get(hass).async_update(area.id, labels={label.label_id})
    freezer.tick(_AGED)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(label.label_id)) is None


async def test_label_used_by_automation_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a label targeted by an automation is left alone."""
    label = lr.async_get(hass).async_create("Targeted")
    freezer.tick(_AGED)
    monkeypatch.setattr(
        unused_labels,
        "automations_with_label",
        lambda _hass, lid: ["automation.lights"] if lid == label.label_id else [],
    )

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(label.label_id)) is None


async def test_label_used_by_script_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a label targeted by a script is left alone."""
    label = lr.async_get(hass).async_create("Targeted")
    freezer.tick(_AGED)
    monkeypatch.setattr(
        unused_labels,
        "scripts_with_label",
        lambda _hass, lid: ["script.lights"] if lid == label.label_id else [],
    )

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(label.label_id)) is None


async def test_fix_flow_remove_option_removes_label(
    hass: HomeAssistant,
) -> None:
    """Test the remove menu option deletes the label."""
    label = lr.async_get(hass).async_create("Holiday")

    flow = await async_create_fix_flow(
        hass,
        _issue_id(label.label_id),
        {"unused_label_id": label.label_id, "label": "Holiday"},
    )
    assert isinstance(flow, UnusedLabelFixFlow)
    flow.hass = hass
    flow.data = {"unused_label_id": label.label_id, "label": "Holiday"}

    menu = await flow.async_step_init()
    assert menu["type"] == FlowResultType.MENU
    assert lr.async_get(hass).async_get_label(label.label_id) is not None

    result = await flow.async_step_remove()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert lr.async_get(hass).async_get_label(label.label_id) is None


async def test_fix_flow_ignore_option_dismisses_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the keep menu option ignores the issue and keeps the label."""
    label = lr.async_get(hass).async_create("Targeted")
    freezer.tick(_AGED)
    await SpookRepair(hass).async_inspect()
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(label.label_id))

    flow = _flow_for(hass, label.label_id, "Targeted")
    result = await flow.async_step_ignore()

    assert result["type"] == FlowResultType.ABORT
    assert lr.async_get(hass).async_get_label(label.label_id) is not None
    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(label.label_id))
    assert issue is not None
    assert issue.dismissed_version is not None
