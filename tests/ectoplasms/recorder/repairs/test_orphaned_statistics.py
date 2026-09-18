"""Tests for the orphaned long-term statistics repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.recorder import DATA_INSTANCE

from custom_components.spook import statistics_sources
from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.recorder.repairs import orphaned_statistics
from custom_components.spook.ectoplasms.recorder.repairs.orphaned_statistics import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er, issue_registry as ir
    import pytest

_ISSUE_ID = "orphaned_statistics_orphaned_statistics"


def _install_fake_recorder(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    validation: dict[str, list[Any]],
    recorded: dict[str, str | None] | None = None,
) -> None:
    """Install a fake recorder instance returning the given validation.

    `recorded` is what the recorder holds by way of metadata for those IDs:
    the name each was published under, or `None` for one a sensor wrote
    itself. Everything validated is recorded under no name unless said
    otherwise.
    """

    async def _async_add_executor_job(_func: Any, *_args: Any) -> Any:
        return validation

    hass.data[DATA_INSTANCE] = SimpleNamespace(
        async_add_executor_job=_async_add_executor_job,
    )
    monkeypatch.setattr(orphaned_statistics, "validate_statistics", lambda _hass: None)

    names = dict.fromkeys(validation) | (recorded or {})

    async def _async_metadata(
        _func: Any,
        *_args: Any,
    ) -> dict[str, tuple[int, dict[str, Any]]]:
        return {
            statistic_id: (1, {"name": name}) for statistic_id, name in names.items()
        }

    monkeypatch.setattr(
        statistics_sources,
        "get_instance",
        lambda hass: SimpleNamespace(  # noqa: ARG005
            async_add_executor_job=_async_metadata,
        ),
    )


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


async def test_statistics_published_on_purpose_are_not_orphans(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An integration can publish statistics with no entity behind them.

    Home Assistant makes it name them after one, so a gas meter read by a
    service arrives as `sensor.something` with no state, and the recorder
    validation calls that `no_state` all the same. The energy dashboard
    draws it perfectly happily. Following the repair here would delete
    working history. #1625.
    """
    validation = {
        "sensor.gazpar_energy": [SimpleNamespace(type="no_state")],
        "sensor.ghost": [SimpleNamespace(type="no_state")],
    }
    _install_fake_recorder(
        hass,
        monkeypatch,
        validation,
        recorded={"sensor.gazpar_energy": "Gazpar energy"},
    )

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["statistics"] == "- `sensor.ghost`"


async def test_a_registered_entity_without_a_state_is_not_an_orphan(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabled, or not set up yet: Home Assistant knows exactly what it is.

    Its statistics are waiting for it, not left behind by it. #1625.
    """
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "resting",
        suggested_object_id="resting",
    )
    validation = {"sensor.resting": [SimpleNamespace(type="no_state")]}
    _install_fake_recorder(hass, monkeypatch, validation)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None
