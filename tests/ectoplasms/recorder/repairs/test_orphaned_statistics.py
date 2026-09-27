"""Tests for the orphaned long-term statistics repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.recorder import DATA_INSTANCE

from custom_components.spook import statistics_sources
from custom_components.spook.ectoplasms.recorder.repairs.orphaned_statistics import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er, issue_registry as ir
    import pytest

_ISSUE_ID = "orphaned_statistics_orphaned_statistics"

# Comfortably past the repair's settling time, so a second look confirms
# what the first one suspected.
_LONG_ENOUGH = timedelta(minutes=20)


async def _inspect_until_settled(
    repair: SpookRepair,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Look twice, far enough apart for a suspicion to be confirmed.

    Nothing is reported on a single sighting, so a test that wants to see an
    issue has to give the repair the second look it waits for.
    """
    await repair.async_inspect()
    freezer.tick(_LONG_ENOUGH)
    await repair.async_inspect()


def _install_fake_recorder(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    validation: dict[str, list[Any]],
    recorded: dict[str, str | None] | None = None,
) -> None:
    """Stand in for the recorder, answering with the given validation.

    `recorded` is what the recorder holds by way of metadata for those IDs:
    the name each was published under, or `None` for one a sensor wrote
    itself. Everything validated is recorded under no name unless said
    otherwise.

    The executor really calls what it is handed, so the two questions Spook
    asks stay told apart: which statistics have no state, and which of those
    were published on purpose.

    `validation` is read on every call rather than copied, so a test that
    needs the answer to change part way through mutates the mapping it
    passed in.
    """
    names = dict.fromkeys(validation) | (recorded or {})

    monkeypatch.setattr(
        statistics_sources, "validate_statistics", lambda _hass: validation
    )
    monkeypatch.setattr(
        statistics_sources,
        "get_metadata",
        lambda _hass, statistic_ids: {
            statistic_id: (1, {"name": names.get(statistic_id)})
            for statistic_id in statistic_ids
        },
    )

    async def _async_add_executor_job(func: Any, *args: Any) -> Any:
        """Run it here, the way the recorder would run it over there."""
        return func(*args)

    instance = SimpleNamespace(async_add_executor_job=_async_add_executor_job)
    hass.data[DATA_INSTANCE] = instance
    monkeypatch.setattr(statistics_sources, "get_instance", lambda _hass: instance)


async def test_orphaned_statistics_create_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test statistics with a no_state issue are reported."""
    validation = {
        "sensor.ghost": [SimpleNamespace(type="no_state")],
        "sensor.excluded": [SimpleNamespace(type="entity_no_longer_recorded")],
        "sensor.fine": [],
    }
    _install_fake_recorder(hass, monkeypatch, validation)

    await _inspect_until_settled(SpookRepair(hass), freezer)

    issue = async_issue_about(issue_registry, _ISSUE_ID)
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

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def test_recorder_not_set_up_is_a_no_op(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair does nothing when the recorder is not set up."""
    hass.data.pop(DATA_INSTANCE, None)

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def test_statistics_published_on_purpose_are_not_orphans(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
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

    await _inspect_until_settled(SpookRepair(hass), freezer)

    issue = async_issue_about(issue_registry, _ISSUE_ID)
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

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def test_a_sensor_gone_for_a_moment_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test one sighting is not enough to call a sensor's history abandoned.

    A working sensor is briefly in neither the state machine nor the registry
    more often than it sounds: an integration re-registering its entities, a
    config entry reloading, the moments during a start before everything has
    arrived. A Companion app battery sensor reported as an orphan while it
    was recording history perfectly well is #1672.
    """
    validation = {"sensor.sm_g980f_battery_level": [SimpleNamespace(type="no_state")]}
    _install_fake_recorder(hass, monkeypatch, validation)
    repair = SpookRepair(hass)

    await repair.async_inspect()

    assert async_issue_about(issue_registry, _ISSUE_ID) is None

    # Back before the settling time is up, which is what those windows look
    # like from here.
    freezer.tick(timedelta(minutes=1))
    validation.clear()
    await repair.async_inspect()

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def test_a_sensor_that_comes_back_starts_the_wait_over(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the clock does not keep running across a sensor being back.

    Otherwise a sensor that drops out for a moment once an hour collects
    enough sightings to be reported eventually, which is the false positive
    arriving slowly rather than not at all.
    """
    gone = {"sensor.sm_g980f_battery_level": [SimpleNamespace(type="no_state")]}
    validation: dict[str, list[Any]] = dict(gone)
    _install_fake_recorder(hass, monkeypatch, validation)
    repair = SpookRepair(hass)

    for _ in range(4):
        validation.clear()
        validation.update(gone)
        await repair.async_inspect()

        freezer.tick(_LONG_ENOUGH)
        validation.clear()
        await repair.async_inspect()

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def test_a_sensor_that_stays_gone_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test waiting does not mean never saying anything.

    Statistics really left behind are what this repair is for, and they are
    still reported once they have kept looking that way.
    """
    validation = {"sensor.ghost": [SimpleNamespace(type="no_state")]}
    _install_fake_recorder(hass, monkeypatch, validation)

    await _inspect_until_settled(SpookRepair(hass), freezer)

    issue = async_issue_about(issue_registry, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["statistics"] == "- `sensor.ghost`"


async def test_the_issue_carries_what_the_fix_is_dispatched_on(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the issue is fixable and names its findings the agreed way.

    Which flow opens is decided by a key in the issue's data, and the flow's
    own tests build that data by hand. So a typo here would leave the real
    repair on Home Assistant's plain confirm flow, offering nothing, with
    every test of the fix still passing.
    """
    validation = {
        "sensor.ghost": [SimpleNamespace(type="no_state")],
        "sensor.gone": [SimpleNamespace(type="no_state")],
    }
    _install_fake_recorder(hass, monkeypatch, validation)

    await _inspect_until_settled(SpookRepair(hass), freezer)

    issue = async_issue_about(issue_registry, _ISSUE_ID)
    assert issue
    assert issue.is_fixable
    assert issue.data == {"orphaned_statistic_ids": "sensor.ghost,sensor.gone"}
