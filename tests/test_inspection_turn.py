"""Tests for the repairs taking turns to look.

One repair looks at a time, so a look that never ends, like a question to
the recorder that is never answered, holds up every repair waiting behind
it. These pin the ways out: nothing waits that has no reason to look, and
reloading Spook gives its repairs a turn of their own.
"""
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant import core as ha_core
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState, Event, callback

from custom_components import spook
from custom_components.spook.const import DOMAIN
from custom_components.spook.repairs import AbstractSpookRepair, SpookRepairManager

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


class _CountingRepair(AbstractSpookRepair):
    """Repair that counts its rounds and its looks."""

    domain = "mock"
    repair = "mock_counting"

    #: Hold on to the turn until let go, the way a look that waits on a
    #: question to the recorder does.
    holds_on = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self.rounds_started = 0
        self.rounds_ended = 0
        self.looks = 0
        self.looking = asyncio.Event()
        self.let_go = asyncio.Event()

    @property
    def round_pending(self) -> bool:
        """Return whether a round of this repair started and has not ended."""
        return self.rounds_started > self.rounds_ended

    async def _async_inspect_with_cleanup(self) -> None:
        """Run a round, counting it, however it ends."""
        self.rounds_started += 1
        try:
            await super()._async_inspect_with_cleanup()
        finally:
            self.rounds_ended += 1

    async def async_inspect(self) -> None:
        """Look, and hold on to the turn if told to."""
        self.looks += 1
        self.looking.set()
        if self.holds_on:
            await self.let_go.wait()


class _StuckRepair(_CountingRepair):
    """Repair whose look waits on a database that never answers."""

    repair = "mock_stuck"
    holds_on = True


class _ReportingRepair(_CountingRepair):
    """Repair that finds something every time it looks."""

    repair = "mock_reporting"

    async def async_inspect(self) -> None:
        """Look, and report what is found."""
        await super().async_inspect()
        self.async_create_issue(issue_id="found")


class _OtherStuckRepair(_StuckRepair):
    """A second repair that holds on, set up alongside the first."""

    repair = "mock_other_stuck"


def _module(repair_class: type[AbstractSpookRepair]) -> SimpleNamespace:
    """Return a stand-in repair module for the repair manager."""
    return SimpleNamespace(
        __name__=f"mock.{repair_class.repair}", SpookRepair=repair_class
    )


def _repair_of[RepairT: AbstractSpookRepair](
    manager: SpookRepairManager, repair_class: type[RepairT]
) -> RepairT:
    """Return the one repair of this class the manager set up."""
    # By the exact class: the stand-in repairs build on one another, so
    # `isinstance` would find the ones built on this class as well.
    (repair,) = (
        repair
        for repair in manager.repairs
        if type(repair) is repair_class  # pylint: disable=unidiomatic-typecheck
    )
    return repair


async def _let_tasks_run() -> None:
    """Give tasks started along the way their turns, without waiting for all.

    Not `async_block_till_done`: that waits for the look that never ends.
    """
    for _ in range(10):
        await asyncio.sleep(0)


async def _come_due(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the time pass a repair waits before it looks, and its round start."""
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await _let_tasks_run()


async def _async_holding_the_turn(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> _StuckRepair:
    """Return a repair made on its own, looking and holding on to the turn."""
    holder = _StuckRepair(hass)
    await holder.async_activate()
    await _come_due(hass, freezer)
    assert holder.looking.is_set()
    return holder


async def test_a_round_due_while_stopping_does_not_wait_for_the_turn(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a look that comes due while Home Assistant stops does not queue.

    Home Assistant waits for what is started while it stops. A round waiting
    behind a look that never ends held up its stop until it gave up on it.
    """
    holder = await _async_holding_the_turn(hass, freezer)
    other = _CountingRepair(hass)

    hass.set_state(CoreState.stopping)
    await other.async_activate()
    await _come_due(hass, freezer)

    assert other.rounds_started == 1
    assert not other.round_pending
    assert other.looks == 0

    hass.set_state(CoreState.running)
    holder.let_go.set()
    await hass.async_block_till_done()
    await holder.async_deactivate()
    await other.async_deactivate()


async def test_a_round_of_a_deactivated_repair_does_not_wait_for_the_turn(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a round of a repair that is gone ends without waiting."""
    holder = await _async_holding_the_turn(hass, freezer)
    other = _CountingRepair(hass)
    await other.async_activate()
    await other.async_deactivate()

    hass.async_create_task(other._async_inspect_with_cleanup())
    await _let_tasks_run()

    assert other.rounds_started == 1
    assert not other.round_pending
    assert other.looks == 0

    holder.let_go.set()
    await hass.async_block_till_done()
    await holder.async_deactivate()


async def test_deactivating_calls_off_a_round_waiting_for_its_turn(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test deactivating a repair ends the round of it that waits its turn.

    Shutting the debouncer down stops the next round, not one already
    waiting. Behind a look that never ends, that one waited for as long as
    Home Assistant ran, one more with every reload of Spook.
    """
    holder = _StuckRepair(hass)
    other = _CountingRepair(hass)
    await holder.async_activate()
    await other.async_activate()
    await _come_due(hass, freezer)
    assert holder.looking.is_set()
    assert other.round_pending

    await other.async_deactivate()
    await _let_tasks_run()

    assert not other.round_pending
    assert other.looks == 0

    # Calling the wait off leaves the turn to whoever has it, and free once
    # they are done with it.
    holder.let_go.set()
    await hass.async_block_till_done()
    assert not holder.round_pending
    await holder.async_deactivate()

    late = _CountingRepair(hass)
    await late.async_activate()
    await _come_due(hass, freezer)
    assert late.looks == 1
    await late.async_deactivate()


async def test_repairs_of_one_setup_take_turns(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test two repairs of the same setup never look at the same time.

    Taking turns is what keeps each stretch of work to one round, see the
    inspection turn in the repairs module.
    """
    manager = SpookRepairManager(hass)
    await manager._async_setup_repair_module(_module(_StuckRepair))
    await manager._async_setup_repair_module(_module(_OtherStuckRepair))
    first = _repair_of(manager, _StuckRepair)
    second = _repair_of(manager, _OtherStuckRepair)

    await _come_due(hass, freezer)

    assert first.round_pending
    assert second.round_pending
    looking, waiting = (first, second) if first.looking.is_set() else (second, first)
    assert looking.looking.is_set()
    assert not waiting.looking.is_set()

    looking.let_go.set()
    await _let_tasks_run()

    assert waiting.looking.is_set()

    waiting.let_go.set()
    await hass.async_block_till_done()
    await manager.async_on_unload()


async def test_a_stuck_look_does_not_hold_up_the_next_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repairs of a new setup look while one of the old is stuck.

    Reloading Spook is what anybody does when it stops doing anything. With
    one turn for the whole process, the new repairs queued behind the look
    of the old setup that never ended, and nothing was looked at again until
    Home Assistant restarted.
    """
    old = SpookRepairManager(hass)
    await old._async_setup_repair_module(_module(_StuckRepair))
    stuck = _repair_of(old, _StuckRepair)
    await _come_due(hass, freezer)
    assert stuck.round_pending

    await old.async_on_unload()

    new = SpookRepairManager(hass)
    await new._async_setup_repair_module(_module(_ReportingRepair))
    reporting = _repair_of(new, _ReportingRepair)
    await _come_due(hass, freezer)

    assert reporting.looks == 1
    assert not reporting.round_pending
    assert issue_registry.async_get_issue(DOMAIN, "mock_reporting_found")

    # The old look ends some day, and changes nothing when it does.
    assert stuck.round_pending
    stuck.let_go.set()
    await hass.async_block_till_done()
    assert not stuck.round_pending
    await new.async_on_unload()


class _MockModulesRepairManager(SpookRepairManager):
    """Repair manager setting up a stuck repair and a reporting one."""

    async def async_setup(self, *, spread_first_inspections: bool = False) -> None:
        """Set up the two stand-in repairs, and none of Spook's own."""
        del spread_first_inspections
        await self._async_setup_repair_module(_module(_StuckRepair))
        await self._async_setup_repair_module(_module(_ReportingRepair))


@pytest.mark.usefixtures("skip_dependency_setup")
async def test_reloading_spook_is_a_way_out_of_a_stuck_look(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a reload of Spook gets its repairs looking again.

    The way it went wrong: a repair asks the recorder and is never answered,
    every other repair waits behind it, and the reload a person tries next
    set up repairs that waited behind it as well.
    """

    async def _async_forward_no_platforms(
        _hass: HomeAssistant, _entry: ConfigEntry
    ) -> None:
        """Forward no ectoplasm setup."""

    class _NoServices:
        def __init__(self, hass: HomeAssistant) -> None:
            self.hass = hass

        async def async_setup(self) -> None:
            """Set up no services."""

        def async_on_unload(self) -> None:
            """Unload no services."""

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", lambda _hass: set())
    monkeypatch.setattr(spook, "async_forward_setup_entry", _async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _NoServices)
    monkeypatch.setattr(spook, "SpookRepairManager", _MockModulesRepairManager)
    hass.set_state(CoreState.running)

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    first_setup: SpookRepairManager = entry.runtime_data
    stuck = _repair_of(first_setup, _StuckRepair)
    await _come_due(hass, freezer)

    # Whichever of the two went first, the database never answers, so the
    # stuck one ends up with the turn and keeps it.
    await _come_due(hass, freezer)
    assert stuck.looking.is_set()
    assert stuck.round_pending
    issue_registry.async_delete(DOMAIN, "mock_reporting_found")

    # The one question that was lost stays lost. Asked again, it is answered.
    monkeypatch.setattr(_StuckRepair, "holds_on", False)

    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    second_setup: SpookRepairManager = entry.runtime_data
    assert second_setup is not first_setup
    reporting = _repair_of(second_setup, _ReportingRepair)
    await _come_due(hass, freezer)

    assert reporting.looks == 1
    assert issue_registry.async_get_issue(DOMAIN, "mock_reporting_found")

    stuck.let_go.set()
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_stopping_with_a_stuck_look_does_not_wait_it_out(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a stuck look does not hold up the stop of Home Assistant.

    Home Assistant does not wait for what was running before it started to
    stop: it cancels that once its last stage comes. What starts while it
    stops, it waits for, stage after stage, and a round coming due then
    waited for its turn behind the stuck look until each stage gave up.

    Real time, no frozen clock: a frozen one keeps those stages from ever
    giving up, and the stop would never end. The stages give up after a
    second here instead of minutes, so a round that holds them up shows up
    as a stage that timed out without making the test take minutes.
    """
    for stage_timeout in (
        "STOP_STAGE_SHUTDOWN_TIMEOUT",
        "FINAL_WRITE_STAGE_SHUTDOWN_TIMEOUT",
        "CLOSE_STAGE_SHUTDOWN_TIMEOUT",
    ):
        monkeypatch.setattr(ha_core, stage_timeout, 1)

    holder = _StuckRepair(hass)
    other = _CountingRepair(hass)
    hass.async_create_task(holder._async_inspect_with_cleanup())
    await holder.looking.wait()

    @callback
    def _a_round_comes_due(_: Event) -> None:
        """Start a round of the other repair, the way its debouncer does."""
        hass.async_create_task(other._async_inspect_with_cleanup())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _a_round_comes_due)

    caplog.set_level(logging.WARNING, logger="homeassistant.core")
    async with asyncio.timeout(30):
        await hass.async_stop()

    assert other.rounds_started == 1
    assert other.looks == 0
    assert "Timed out" not in caplog.text

    # The stuck look itself was running before the stop, and is cancelled
    # once the last stage comes.
    assert not holder.round_pending
