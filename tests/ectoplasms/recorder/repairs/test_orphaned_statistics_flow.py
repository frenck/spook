"""Tests for clearing orphaned long-term statistics from the repair itself.

Clearing statistics is a websocket command the Statistics page calls and no
action anybody can reach, so without this the only way to act on the report
is to work through that page by hand. On a couple of hundred entries that is
not really an offer at all. #1613.
"""

# The flow's steps are what there is to drive, and its data is private.
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.recorder import DATA_INSTANCE

from custom_components.spook import repairs, statistics_sources
from custom_components.spook.statistics_sources import (
    DATA_ABANDONED_SINCE,
    async_settled_orphaned_statistic_ids,
)
from custom_components.spook.repairs import (
    OrphanedStatisticsFixFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    import pytest

_ISSUE_ID = "orphaned_statistics_orphaned_statistics"

# Comfortably past the settling time a statistic has to survive before Spook
# will say anything about it, let alone offer to delete it.
_LONG_ENOUGH = timedelta(minutes=20)


async def _settle(hass: HomeAssistant) -> None:
    """Let whatever is missing now have been missing long enough.

    The fix asks the same question the report asked, settling time and all,
    so a test that wants the button to do something has to give it findings
    that have earned their place.

    Done by putting the clock back on what was seen rather than by freezing
    time. The flow waits on the recorder with `asyncio.timeout`, and a
    frozen clock is one that never runs out.
    """
    await async_settled_orphaned_statistic_ids(hass)
    hass.data[DATA_ABANDONED_SINCE] = {
        statistic_id: first_seen - _LONG_ENOUGH
        for statistic_id, first_seen in hass.data[DATA_ABANDONED_SINCE].items()
    }


def _install_fake_recorder(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    abandoned: set[str],
    *,
    confirms: bool = True,
) -> list[list[str]]:
    """Stand in for the recorder, and record what it is asked to clear.

    `confirms` is whether it gets round to saying it is done. A recorder
    with a long queue in front of it, or one that is wedged, does not.
    """
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

    def _async_clear_statistics(
        statistic_ids: list[str],
        *,
        on_done: Any = None,
    ) -> None:
        """Take the work on, and say so afterwards the way the recorder does."""
        cleared.append(list(statistic_ids))
        if confirms and on_done is not None:
            on_done()

    instance = SimpleNamespace(
        async_add_executor_job=_async_add_executor_job,
        async_clear_statistics=_async_clear_statistics,
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
    await _settle(hass)

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
    await _settle(hass)

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
    await _settle(hass)

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


async def test_a_recorder_that_does_not_answer_is_not_a_success(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test asking is not the same as it having happened.

    The recorder takes the work on its own thread and says when it lands.
    Closing the issue on the strength of having asked would make a wedged
    recorder look like a job well done, and the statistics would still be
    there with nothing left to point at them.
    """
    cleared = _install_fake_recorder(
        hass, monkeypatch, {"sensor.ghost"}, confirms=False
    )
    await _settle(hass)

    monkeypatch.setattr(repairs, "_CLEARING_TAKES_AT_MOST", 0.01)

    result = await _flow(hass, "sensor.ghost").async_step_remove()

    # It was asked for, and it may still land. What it is not is finished.
    assert cleared == [["sensor.ghost"]]
    assert result["type"] == "abort"
    assert result["reason"] == "clearing_took_too_long"


async def test_one_that_came_back_and_dipped_again_is_left_alone(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a fresh glance is not enough to delete somebody's history.

    An issue can sit unopened for days. In that time a sensor can come back,
    work perfectly well, and then be missing again for a moment because its
    integration happened to be reloading when the button was pressed. A fix
    that only asks whether it is gone right now would take that moment as
    permission, which is exactly the case the settling time exists for.
    """
    missing = {"sensor.ghost", "sensor.flapper"}
    cleared = _install_fake_recorder(hass, monkeypatch, missing)
    await _settle(hass)

    # The flapper comes back, and Spook notices on its next round.
    missing.discard("sensor.flapper")
    await async_settled_orphaned_statistic_ids(hass)

    # And is away again by the time somebody opens the repair.
    missing.add("sensor.flapper")

    await _flow(hass, "sensor.ghost,sensor.flapper").async_step_remove()

    assert cleared == [["sensor.ghost"]]
