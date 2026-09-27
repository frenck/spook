"""Tests for clearing orphaned long-term statistics from the repair itself.

Clearing statistics is a websocket command the Statistics page calls and no
action anybody can reach, so without this the only way to act on the report
is to work through that page by hand. On a couple of hundred entries that is
not really an offer at all. #1613.
"""

# The flow's steps are what there is to drive, and its data is private.
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.recorder import DATA_INSTANCE

from custom_components.spook import statistics_sources
from custom_components.spook.repairs import (
    OrphanedStatisticsFixFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    import pytest

_ISSUE_ID = "orphaned_statistics_orphaned_statistics"


def _install_fake_recorder(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    abandoned: set[str],
) -> list[list[str]]:
    """Stand in for the recorder, and record what it is asked to clear."""
    cleared: list[list[str]] = []

    monkeypatch.setattr(
        statistics_sources,
        "validate_statistics",
        lambda _hass: {
            statistic_id: [SimpleNamespace(type="no_state")]
            for statistic_id in abandoned
        },
    )
    monkeypatch.setattr(
        statistics_sources,
        "get_metadata",
        lambda _hass, statistic_ids: {
            statistic_id: (1, {"name": None}) for statistic_id in statistic_ids
        },
    )

    async def _async_add_executor_job(func: Any, *args: Any) -> Any:
        return func(*args)

    instance = SimpleNamespace(
        async_add_executor_job=_async_add_executor_job,
        async_clear_statistics=lambda ids, **_kwargs: cleared.append(list(ids)),
    )
    hass.data[DATA_INSTANCE] = instance
    monkeypatch.setattr(statistics_sources, "get_instance", lambda _hass: instance)
    monkeypatch.setattr(
        "custom_components.spook.repairs.get_instance", lambda _hass: instance
    )

    return cleared


def _flow(hass: HomeAssistant, offered: str) -> OrphanedStatisticsFixFlow:
    """Return the flow, wired the way the repairs component wires it."""
    flow = OrphanedStatisticsFixFlow()
    flow.hass = hass
    flow.issue_id = _ISSUE_ID
    flow.data = {"orphaned_statistic_ids": offered}
    return flow


async def test_the_flow_is_chosen_for_this_issue(hass: HomeAssistant) -> None:
    """Dispatch is on the data key, so this is what wires the two together."""
    flow = await async_create_fix_flow(
        hass, _ISSUE_ID, {"orphaned_statistic_ids": "sensor.ghost"}
    )

    assert isinstance(flow, OrphanedStatisticsFixFlow)


async def test_clearing_throws_away_what_was_offered(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test pressing the button clears the statistics the report named."""
    cleared = _install_fake_recorder(hass, monkeypatch, {"sensor.ghost", "sensor.gone"})

    result = await (_flow(hass, "sensor.ghost,sensor.gone")).async_step_remove()

    assert cleared == [["sensor.ghost", "sensor.gone"]]
    assert result["type"] == "create_entry"


async def test_one_that_came_back_is_left_alone(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the fix looks again rather than trusting the report.

    An issue sits there until somebody opens it, and by then a sensor whose
    integration was slow to start is back. This deletes history, so what goes
    is what both the report and a fresh look agree on.
    """
    cleared = _install_fake_recorder(hass, monkeypatch, {"sensor.ghost"})

    await (_flow(hass, "sensor.ghost,sensor.came_back")).async_step_remove()

    assert cleared == [["sensor.ghost"]]


async def test_nothing_is_cleared_that_was_never_offered(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a statistic that went bad later is not swept up with the rest.

    The list somebody read is the list they agreed to, and something that
    turned orphaned since is not on it.
    """
    cleared = _install_fake_recorder(
        hass, monkeypatch, {"sensor.ghost", "sensor.newly_orphaned"}
    )

    await (_flow(hass, "sensor.ghost")).async_step_remove()

    assert cleared == [["sensor.ghost"]]


async def test_everything_coming_back_clears_nothing(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the fix says so rather than reporting a silent success."""
    cleared = _install_fake_recorder(hass, monkeypatch, set())

    result = await (_flow(hass, "sensor.ghost")).async_step_remove()

    assert not cleared
    assert result["type"] == "abort"
    assert result["reason"] == "nothing_to_clear"


async def test_the_menu_lists_what_will_go(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test somebody is shown the statistics before agreeing to lose them."""
    _install_fake_recorder(hass, monkeypatch, {"sensor.ghost"})

    result = await (_flow(hass, "sensor.ghost,sensor.gone")).async_step_init()

    assert result["description_placeholders"]["statistics"] == (
        "- `sensor.ghost`\n- `sensor.gone`"
    )
