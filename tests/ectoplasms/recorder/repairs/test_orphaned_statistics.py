"""Tests for the orphaned long-term statistics repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.recorder import DATA_INSTANCE

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.recorder.repairs import orphaned_statistics
from custom_components.spook.ectoplasms.recorder.repairs.orphaned_statistics import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir
    import pytest

_ISSUE_ID = "orphaned_statistics_orphaned_statistics"


def _install_fake_recorder(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    validation: dict[str, list[Any]],
) -> None:
    """Install a fake recorder instance returning the given validation."""

    async def _async_add_executor_job(_func: Any, *_args: Any) -> Any:
        return validation

    hass.data[DATA_INSTANCE] = SimpleNamespace(
        async_add_executor_job=_async_add_executor_job,
    )
    monkeypatch.setattr(orphaned_statistics, "validate_statistics", lambda _hass: None)


async def test_orphaned_statistics_create_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test statistics with a no_state issue are reported."""
    validation = {
        "sensor.ghost": [SimpleNamespace(type="no_state")],
        "sensor.excluded": [SimpleNamespace(type="entity_no_longer_recorded")],
        "sensor.fine": [],
    }
    _install_fake_recorder(hass, monkeypatch, validation)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    # Only the no_state orphan is reported, not excluded or fine statistics.
    assert issue.translation_placeholders["statistics"] == "- `sensor.ghost`"


async def test_no_orphans_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test only non-orphan issue types produce no issue."""
    validation = {
        "sensor.excluded": [SimpleNamespace(type="entity_no_longer_recorded")]
    }
    _install_fake_recorder(hass, monkeypatch, validation)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_recorder_not_set_up_is_a_no_op(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair does nothing when the recorder is not set up."""
    hass.data.pop(DATA_INSTANCE, None)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None
