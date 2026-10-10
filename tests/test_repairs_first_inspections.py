"""Tests for the first round of inspections after a start taking turns. #1898."""
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order

from __future__ import annotations

from datetime import datetime, timedelta
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import RANDOM_MICROSECOND_MAX
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook import repairs
from custom_components.spook.repairs import (
    FIRST_INSPECTIONS_SPREAD_OVER,
    AbstractSpookRepair,
    SpookRepairManager,
)
import pytest
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

pytestmark = pytest.mark.usefixtures("skip_dependency_setup")

# The repairs that wait for the recorder, and keep doing so.
_WAITS_FOR_THE_RECORDER = timedelta(minutes=10)

# Long enough for a debouncer's cooldown to run out after a turn comes.
_COOLDOWN_AND_A_BIT = timedelta(seconds=4)

# `async_fire_time_changed` runs every timer due up to this much later too.
_TIMER_SLACK = timedelta(microseconds=RANDOM_MICROSECOND_MAX)


def _module_name(repair: AbstractSpookRepair) -> str:
    """Return the name of the module a repair came from."""
    return type(repair).__module__


async def _async_set_up_repairs(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    *,
    spread_first_inspections: bool,
) -> tuple[SpookRepairManager, list[tuple[datetime, str]]]:
    """Set up every real repair, writing down each inspection as it starts."""
    # The Lovelace repairs want the Lovelace data container while activating.
    hass.data["lovelace"] = SimpleNamespace(dashboards={}, resources=None)

    # The component the tests announce as loaded, again and again.
    assert await async_setup_component(hass, "automation", {})

    inspections: list[tuple[datetime, str]] = []
    activate = SpookRepairManager.async_activate

    async def _async_activate_and_watch(
        self: SpookRepairManager, repair: AbstractSpookRepair
    ) -> None:
        inspect = repair.async_inspect

        async def _async_inspect_and_note() -> None:
            inspections.append((dt_util.utcnow(), repair.repair))
            await inspect()

        monkeypatch.setattr(repair, "async_inspect", _async_inspect_and_note)
        await activate(self, repair)

    monkeypatch.setattr(SpookRepairManager, "async_activate", _async_activate_and_watch)

    manager = SpookRepairManager(hass)
    await manager.async_setup(spread_first_inspections=spread_first_inspections)

    return manager, inspections


async def _async_move_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    duration: timedelta,
) -> None:
    """Let time pass in small steps, so timers armed on the way fire too."""
    step = timedelta(milliseconds=500)
    for _ in range(int(duration / step)):
        freezer.tick(step)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


async def test_turns_are_handed_out_in_a_fixed_order(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test every repair gets its own moment, the same one every start.

    In order of module name, evenly over the window, starting right away.
    The repairs waiting for the recorder keep their own, later moment.
    """
    manager, _ = await _async_set_up_repairs(
        hass, monkeypatch, spread_first_inspections=True
    )

    waiting_for_the_recorder = [
        repair
        for repair in manager._repairs
        if type(repair).first_inspection_delay is not None
    ]
    taking_turns = sorted(
        (
            repair
            for repair in manager._repairs
            if type(repair).first_inspection_delay is None
        ),
        key=_module_name,
    )

    assert waiting_for_the_recorder
    assert all(
        repair.first_inspection_delay == _WAITS_FOR_THE_RECORDER
        for repair in waiting_for_the_recorder
    )

    turn = FIRST_INSPECTIONS_SPREAD_OVER / len(taking_turns)
    assert [repair.first_inspection_delay for repair in taking_turns] == [
        turn * index for index in range(len(taking_turns))
    ]
    assert taking_turns[-1].first_inspection_delay < FIRST_INSPECTIONS_SPREAD_OVER

    # Handed out again, the same way.
    assert repairs._first_inspection_delays(
        [sys.modules[_module_name(repair)] for repair in taking_turns]
    ) == {
        _module_name(repair): repair.first_inspection_delay for repair in taking_turns
    }

    await manager.async_on_unload()


async def test_without_a_start_nobody_waits_for_a_turn(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a reload or a setup on a running instance looks straight away."""
    manager, _ = await _async_set_up_repairs(
        hass, monkeypatch, spread_first_inspections=False
    )

    assert {
        repair.first_inspection_delay
        for repair in manager._repairs
        if type(repair).first_inspection_delay is None
    } == {None}

    await manager.async_on_unload()


async def test_the_first_round_still_completes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test every repair taking a turn has looked once the window is over.

    And not a single one before its turn, however much happens before then:
    those are exactly the events that used to have them all look at once.
    """
    manager, inspections = await _async_set_up_repairs(
        hass, monkeypatch, spread_first_inspections=True
    )
    started = dt_util.utcnow()
    turns = {
        repair.repair: repair.first_inspection_delay
        for repair in manager._repairs
        if type(repair).first_inspection_delay is None
    }
    assert None not in turns.values()

    registry = er.async_get(hass)
    for device in range(10):
        hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "automation"})
        registry.async_get_or_create("sensor", "pulse", f"device_{device}")
        await _async_move_on(hass, freezer, timedelta(seconds=1))

    await _async_move_on(
        hass, freezer, FIRST_INSPECTIONS_SPREAD_OVER + _COOLDOWN_AND_A_BIT
    )

    first_looks: dict[str, timedelta] = {}
    for when, name in inspections:
        first_looks.setdefault(name, when - started)

    # Every one of them, each no sooner than its turn.
    assert set(first_looks) == set(turns)
    assert all(first_looks[name] >= turn - _TIMER_SLACK for name, turn in turns.items())

    await manager.async_on_unload()


async def test_a_finding_shows_up_on_its_turn(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a dangling reference is still reported, only at its repair's turn.

    An integration adding devices before then is not a reason to look early:
    the first look sees how that ended up anyway.
    """
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "spooky",
                "alias": "Spooky",
                "triggers": {"trigger": "state", "entity_id": "binary_sensor.ghost"},
                "actions": {
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.ghost"},
                },
            },
        },
    )
    manager, _ = await _async_set_up_repairs(
        hass, monkeypatch, spread_first_inspections=True
    )
    (repair,) = (
        repair
        for repair in manager._repairs
        if repair.repair == "automation_unknown_entity_references"
    )
    turn = repair.first_inspection_delay
    assert turn is not None
    assert turn > _COOLDOWN_AND_A_BIT

    registry = er.async_get(hass)
    for device in range(int((turn - _COOLDOWN_AND_A_BIT).total_seconds())):
        hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "automation"})
        registry.async_get_or_create("sensor", "pulse", f"device_{device}")
        await _async_move_on(hass, freezer, timedelta(seconds=1))

    assert not async_issue_about(
        issue_registry, "automation_unknown_entity_references_automation.spooky"
    )

    await _async_move_on(hass, freezer, _COOLDOWN_AND_A_BIT * 2)

    issue = async_issue_about(
        issue_registry, "automation_unknown_entity_references_automation.spooky"
    )
    assert issue
    assert issue.translation_placeholders
    assert "light.ghost" in issue.translation_placeholders["entities"]

    await manager.async_on_unload()
