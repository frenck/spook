"""Tests for Spook repair cleanup."""
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order

from __future__ import annotations

import asyncio

from datetime import timedelta
import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    get_scheduled_timer_handles,
)

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntryChange,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.core import HassJob
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.util import dt as dt_util

from custom_components.spook import repairs
from custom_components.spook.const import DOMAIN
from custom_components.spook.repairs import (
    AbstractSpookEntityComponentUnknownReferencesRepair,
    AbstractSpookRepair,
    AbstractSpookRepairBase,
)

EXPECTED_UNSUBSCRIBE_COUNT = 4
EXPECTED_INTERVAL_INSPECTIONS = 2
EXPECTED_UNCHANGED_INSPECTIONS = 2
EXPECTED_CHANGED_INSPECTIONS = 3
EXPECTED_SUBENTRY_INSPECTIONS = 4
EXPECTED_RENAMED_INSPECTIONS = 5
EXPECTED_DISABLED_INSPECTIONS = 6
EXPECTED_LOOKED_AGAIN_INSPECTIONS = 2
ROUNDS_UP_TO_THE_FAILURE = 2
ROUNDS_UP_TO_THE_LOOK_ONCE_MORE = 3
ROUNDS_UP_TO_THE_NEXT_FAILURE = 4
ROUNDS_UP_TO_THE_NEXT_LOOK_ONCE_MORE = 5

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    import pytest
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


class MockRepairBase(AbstractSpookRepairBase):
    """Mock base repair."""

    domain = "mock"
    repair = "mock_repair"

    async def async_activate(self) -> None:
        """Activate the repair."""

    async def async_inspect(self) -> None:
        """Inspect the repair."""

    async def async_deactivate(self) -> None:
        """Deactivate the repair."""
        await super().async_deactivate()


class MockRepair(AbstractSpookRepair):
    """Mock repair."""

    domain = "mock"
    repair = "mock_repair"
    inspect_events = {"mock_event"}
    inspect_config_entry_changed = True
    inspect_on_reload = True
    inspect_interval = timedelta(days=1)

    inspections = 0

    async def async_inspect(self) -> None:
        """Inspect the repair."""
        self.inspections += 1


async def test_deactivate_leaves_what_it_reported_alone(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deactivating is not the same as the problem being over.

    It happens on every reload, every integration reload and every update, and
    taking the issues down took the "ignore" anybody had pressed with them.
    """
    deleted: list[tuple[str, str]] = []

    def async_delete_issue(
        _hass: HomeAssistant,
        domain: str,
        issue_id: str,
    ) -> None:
        """Capture deleted issues."""
        deleted.append((domain, issue_id))

    monkeypatch.setattr(repairs.ir, "async_delete_issue", async_delete_issue)

    repair = MockRepairBase(hass)
    repair.issue_ids = {"one", "two"}

    await repair.async_deactivate()

    assert repair.issue_ids == {"one", "two"}
    assert not deleted


async def test_deactivate_unsubscribes_all_activation_listeners(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test repair deactivation unsubscribes every activation listener."""
    unsubscribed = []

    def async_dispatcher_connect(
        hass: HomeAssistant,
        signal: str,
        target: Callable[[ConfigEntryChange, ConfigEntry], Any],
    ) -> Callable[[], None]:
        """Connect a dispatcher listener."""
        del hass, signal, target

        def unsubscribe() -> None:
            """Unsubscribe the listener."""
            unsubscribed.append("dispatcher")

        return unsubscribe

    monkeypatch.setattr(repairs, "async_dispatcher_connect", async_dispatcher_connect)

    repair = MockRepair(hass)
    await repair.async_activate()

    assert len(repair._event_subs) == EXPECTED_UNSUBSCRIBE_COUNT

    await repair.async_deactivate()

    assert len(unsubscribed) == 1
    assert not repair._event_subs


class MockIntervalRepair(AbstractSpookRepair):
    """Mock repair that re-inspects on a fixed interval alone."""

    domain = "mock"
    repair = "mock_repair"
    inspect_interval = timedelta(days=1)

    inspections = 0

    async def async_inspect(self) -> None:
        """Inspect the repair."""
        self.inspections += 1


async def _flush_debouncer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Advance past the inspection debouncer cooldown and let it fire."""
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_inspect_interval_reinspects_over_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an interval-only repair re-inspects as time passes."""
    repair = MockIntervalRepair(hass)
    await repair.async_activate()

    # A single timer subscription, no events wired.
    assert len(repair._event_subs) == 1

    # The initial activation bounce runs one inspection.
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == 1

    # A day later the interval fires another inspection.
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_INTERVAL_INSPECTIONS

    # After deactivation the timer no longer fires.
    await repair.async_deactivate()
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_INTERVAL_INSPECTIONS


async def test_config_entry_update_without_changes_skips_inspection(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A config entry that only changed state is no reason to look again.

    UPDATED fires on bare state transitions too, like every attempt of a
    setup that keeps failing, and each one used to run a full inspection.
    #2034.
    """
    entry = MockConfigEntry(
        domain="mock",
        data={"key": "value"},
        entry_id="0123456789abcdef0123456789abcdef",
    )
    repair = MockRepair(hass)
    await repair.async_activate()
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == 1

    # The first UPDATED gets a look: what it holds may really have changed.
    async_dispatcher_send(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.UPDATED, entry
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_UNCHANGED_INSPECTIONS

    # The same data again, like a setup retry firing, gets none.
    async_dispatcher_send(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.UPDATED, entry
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_UNCHANGED_INSPECTIONS

    # New data gets none either: no repair reads it, and it is where an
    # integration keeps its tokens, so every token refresh fires UPDATED.
    refreshed = MockConfigEntry(
        domain="mock",
        data={"key": "value", "token": "refreshed"},
        entry_id="0123456789abcdef0123456789abcdef",
    )
    async_dispatcher_send(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.UPDATED, refreshed
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_UNCHANGED_INSPECTIONS

    # New options on the same entry are a real change, and do get one.
    changed = MockConfigEntry(
        domain="mock",
        data={"key": "value"},
        options={"key": "changed"},
        entry_id="0123456789abcdef0123456789abcdef",
    )
    async_dispatcher_send(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.UPDATED, changed
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_CHANGED_INSPECTIONS

    # A changed subentry leaves data and options alone but rides along on
    # UPDATED, and does get a look too.
    with_subentry = MockConfigEntry(
        domain="mock",
        data={"key": "value"},
        options={"key": "changed"},
        entry_id="0123456789abcdef0123456789abcdef",
        subentries_data=[
            {
                "subentry_id": "fedcba9876543210fedcba9876543210",
                "subentry_type": "test",
                "title": "Sub",
                "data": {"sub": "data"},
            },
        ],
    )
    async_dispatcher_send(
        hass,
        SIGNAL_CONFIG_ENTRY_CHANGED,
        ConfigEntryChange.UPDATED,
        with_subentry,
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_SUBENTRY_INSPECTIONS

    # A rename leaves everything the fingerprint held alone but rides along
    # on UPDATED too, and does get a look.
    renamed = MockConfigEntry(
        domain="mock",
        data={"key": "value"},
        options={"key": "changed"},
        entry_id="0123456789abcdef0123456789abcdef",
        subentries_data=[
            {
                "subentry_id": "fedcba9876543210fedcba9876543210",
                "subentry_type": "test",
                "title": "Sub",
                "data": {"sub": "data"},
            },
        ],
        title="Renamed",
    )
    async_dispatcher_send(
        hass,
        SIGNAL_CONFIG_ENTRY_CHANGED,
        ConfigEntryChange.UPDATED,
        renamed,
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_RENAMED_INSPECTIONS

    # Disabling the entry does the same.
    disabled = MockConfigEntry(
        domain="mock",
        data={"key": "value"},
        options={"key": "changed"},
        entry_id="0123456789abcdef0123456789abcdef",
        subentries_data=[
            {
                "subentry_id": "fedcba9876543210fedcba9876543210",
                "subentry_type": "test",
                "title": "Sub",
                "data": {"sub": "data"},
            },
        ],
        title="Renamed",
        disabled_by=ConfigEntryDisabler.USER,
    )
    async_dispatcher_send(
        hass,
        SIGNAL_CONFIG_ENTRY_CHANGED,
        ConfigEntryChange.UPDATED,
        disabled,
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_DISABLED_INSPECTIONS

    await repair.async_deactivate()


async def test_config_entry_loading_or_unloading_gets_a_look(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An entry that loaded or unloaded is a reason to look, a retry is not.

    A repair reading what a loaded entry holds finds nothing while the entry
    is still setting up. Skipping the update that says it loaded would leave
    that as the last word.
    """
    entry = MockConfigEntry(
        domain="mock",
        data={"key": "value"},
        entry_id="0123456789abcdef0123456789abcdef",
    )
    repair = MockRepair(hass)
    await repair.async_activate()
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == 1

    async def _state_changes_to(state: ConfigEntryState) -> None:
        entry.mock_state(hass, state)
        async_dispatcher_send(
            hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.UPDATED, entry
        )
        await _flush_debouncer(hass, freezer)

    # The first UPDATED gets a look, whatever it says.
    await _state_changes_to(ConfigEntryState.SETUP_IN_PROGRESS)
    assert repair.inspections == EXPECTED_UNCHANGED_INSPECTIONS

    # A setup that keeps failing goes from one state to the next without
    # ever being loaded, and gets no look.
    await _state_changes_to(ConfigEntryState.SETUP_RETRY)
    await _state_changes_to(ConfigEntryState.SETUP_IN_PROGRESS)
    await _state_changes_to(ConfigEntryState.SETUP_RETRY)
    await _state_changes_to(ConfigEntryState.SETUP_IN_PROGRESS)
    assert repair.inspections == EXPECTED_UNCHANGED_INSPECTIONS

    # Once it loads, it does.
    await _state_changes_to(ConfigEntryState.LOADED)
    assert repair.inspections == EXPECTED_CHANGED_INSPECTIONS

    # And when it starts unloading, and again when that is done: the look
    # at the start may come before everything it brought is gone.
    await _state_changes_to(ConfigEntryState.UNLOAD_IN_PROGRESS)
    assert repair.inspections == EXPECTED_SUBENTRY_INSPECTIONS

    await _state_changes_to(ConfigEntryState.NOT_LOADED)
    assert repair.inspections == EXPECTED_RENAMED_INSPECTIONS

    await repair.async_deactivate()


class MockFailingRepair(AbstractSpookRepair):
    """Mock repair whose inspection can be made to fail."""

    domain = "mock"
    repair = "mock_repair"
    inspect_config_entry_changed = True

    inspections = 0
    raise_on_inspect = False

    async def async_inspect(self) -> None:
        """Inspect the repair."""
        self.inspections += 1
        if self.raise_on_inspect:
            msg = "Inspection went bump in the night"
            raise HomeAssistantError(msg)


class MockSlowRepair(AbstractSpookRepair):
    """Mock repair whose first inspection takes as long as the test wants."""

    domain = "mock"
    repair = "mock_repair"
    inspect_events = {"mock_event"}

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self.inspections = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def async_inspect(self) -> None:
        """Inspect the repair, waiting to be released."""
        self.inspections += 1
        self.started.set()
        await self.release.wait()


async def _let_tasks_run() -> None:
    """Give tasks started along the way their turns, without waiting for all."""
    for _ in range(5):
        await asyncio.sleep(0)


async def test_a_look_asked_for_mid_round_is_not_lost(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a look asked for while a round runs gets a round of its own.

    Home Assistant's debouncer drops a call when its cooldown runs out while
    the function still runs. Whatever changed after the round read it, like
    the new configuration behind an `automation_reloaded`, went unseen.
    """
    repair = MockSlowRepair(hass)
    await repair.async_activate()

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await repair.started.wait()

    # Asked for a look while the first round runs, and the cooldown runs
    # out before that round is done.
    hass.bus.async_fire("mock_event")
    await _let_tasks_run()
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await _let_tasks_run()

    repair.release.set()
    await hass.async_block_till_done()
    await _flush_debouncer(hass, freezer)

    assert repair.inspections == EXPECTED_LOOKED_AGAIN_INSPECTIONS

    # Nothing asked for meanwhile, so nothing more.
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_LOOKED_AGAIN_INSPECTIONS

    await repair.async_deactivate()


async def test_a_look_asked_for_mid_round_is_one_round_when_the_round_ends_first(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a round that ends before the cooldown does gets one round after.

    The look the debouncer has planned anyway and the one asked for again
    are the same look, so they make one round, not two.
    """
    repair = MockSlowRepair(hass)
    await repair.async_activate()

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await repair.started.wait()

    hass.bus.async_fire("mock_event")
    await _let_tasks_run()
    repair.release.set()
    await hass.async_block_till_done()

    await _flush_debouncer(hass, freezer)
    await _flush_debouncer(hass, freezer)

    assert repair.inspections == EXPECTED_LOOKED_AGAIN_INSPECTIONS

    await repair.async_deactivate()


class MockWaitingRepair(MockSlowRepair):
    """Mock repair listening to an event of its own."""

    inspect_events = {"waiting_event"}


async def test_a_look_asked_for_while_waiting_for_the_turn_adds_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a look asked for before the round read anything adds no round.

    The round waiting for its turn reads after the change it was asked
    about, so it sees it, even with the cooldown running out meanwhile.
    """
    holder = MockSlowRepair(hass)
    waiting = MockWaitingRepair(hass)
    waiting.release.set()
    await holder.async_activate()
    await waiting.async_activate()

    # Both rounds start, the first one takes the turn and holds on to it.
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await holder.started.wait()
    await _let_tasks_run()
    assert waiting.inspections == 0

    # Asked for a look while waiting, and the cooldown runs out meanwhile.
    hass.bus.async_fire("waiting_event")
    await _let_tasks_run()
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await _let_tasks_run()

    holder.release.set()
    await hass.async_block_till_done()
    await _flush_debouncer(hass, freezer)
    await _flush_debouncer(hass, freezer)

    assert holder.inspections == 1
    assert waiting.inspections == 1

    await holder.async_deactivate()
    await waiting.async_deactivate()


async def test_config_entry_update_retries_after_failed_inspection(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A look that failed keeps the next identical UPDATED a reason to look.

    The fingerprint for a failed run is dropped, so the same entry data
    still sends the repair back in instead of being skipped for good.
    """
    entry = MockConfigEntry(
        domain="mock",
        data={"key": "value"},
        entry_id="0123456789abcdef0123456789abcdef",
    )
    repair = MockFailingRepair(hass)
    await repair.async_activate()
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == 1

    # The UPDATED gets a look, the look fails.
    repair.raise_on_inspect = True
    async_dispatcher_send(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.UPDATED, entry
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_UNCHANGED_INSPECTIONS

    # The same data again is not skipped: the failed look left no
    # fingerprint behind, so it is a reason to look once more.
    async_dispatcher_send(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.UPDATED, entry
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_CHANGED_INSPECTIONS

    # Once a look lands, the fingerprint holds again and the same data
    # is skipped like before.
    repair.raise_on_inspect = False
    async_dispatcher_send(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.UPDATED, entry
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_SUBENTRY_INSPECTIONS

    async_dispatcher_send(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.UPDATED, entry
    )
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == EXPECTED_SUBENTRY_INSPECTIONS

    await repair.async_deactivate()


class MockStumblingRepair(AbstractSpookRepair):
    """Mock repair that nothing asks to look, whose next looks can fail."""

    domain = "mock"
    repair = "mock_repair"
    automatically_clean_up_issues = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self.inspections = 0
        self.failures_to_come = 0
        self.fails_with: type[Exception] = RuntimeError
        self.current_issue_ids = {"one"}

    async def async_inspect(self) -> None:
        """Inspect the repair, failing if told to."""
        self.inspections += 1
        if self.failures_to_come:
            self.failures_to_come -= 1
            msg = "Inspection went bump in the night"
            raise self.fails_with(msg)

        for issue_id in self.current_issue_ids:
            self.async_create_issue(issue_id=issue_id)


async def _async_activate_and_look(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> MockStumblingRepair:
    """Activate a stumbling repair, and let its first look find issue one."""
    repair = MockStumblingRepair(hass)
    await repair.async_activate()
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == 1

    return repair


async def _async_a_round_that_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    repair: MockStumblingRepair,
    *,
    failures: int = 1,
) -> None:
    """Ask for one look, and have it, and the ones after, fail."""
    repair.failures_to_come = failures
    repair.inspect_debouncer.async_schedule_call()
    await _flush_debouncer(hass, freezer)


def _timers_calling_back_into(
    hass: HomeAssistant, repair: AbstractSpookRepair
) -> list[asyncio.TimerHandle]:
    """Return the timers still to go off that call one of a repair's methods."""
    return [
        handle
        for handle in get_scheduled_timer_handles(hass.loop)
        if not handle.cancelled()
        and handle._args
        and isinstance(job := handle._args[-1], HassJob)
        and getattr(job.target, "__self__", None) is repair
    ]


async def _async_move_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    duration: timedelta,
) -> None:
    """Let time pass, and every look that comes due on the way run."""
    freezer.tick(duration)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await _flush_debouncer(hass, freezer)


async def test_a_failed_round_is_followed_by_one_more_look(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a round that fails looks once more, and that look puts it right.

    Nothing else asked for a look, and for a repair that looks daily nothing
    does for a day. The issue that went stale meanwhile stayed up all along.
    """
    repair = await _async_activate_and_look(hass, freezer)
    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one")

    # Put right, but the round that would have seen it fails.
    repair.current_issue_ids = set()
    await _async_a_round_that_fails(hass, freezer, repair)
    assert repair.inspections == ROUNDS_UP_TO_THE_FAILURE
    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one")

    # Not before the time is up.
    await _async_move_on(
        hass, freezer, repairs.LOOK_ONCE_MORE_AFTER - timedelta(seconds=15)
    )
    assert repair.inspections == ROUNDS_UP_TO_THE_FAILURE

    await _async_move_on(hass, freezer, timedelta(seconds=15))
    assert repair.inspections == ROUNDS_UP_TO_THE_LOOK_ONCE_MORE
    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one") is None

    # Once, and that is it.
    await _async_move_on(hass, freezer, timedelta(hours=1))
    assert repair.inspections == ROUNDS_UP_TO_THE_LOOK_ONCE_MORE

    await repair.async_deactivate()


async def test_a_look_once_more_that_fails_as_well_is_the_last(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed look once more does not start a loop of looks."""
    repair = await _async_activate_and_look(hass, freezer)

    await _async_a_round_that_fails(hass, freezer, repair, failures=5)
    await _async_move_on(hass, freezer, repairs.LOOK_ONCE_MORE_AFTER)
    assert repair.inspections == ROUNDS_UP_TO_THE_LOOK_ONCE_MORE

    for _ in range(10):
        await _async_move_on(hass, freezer, repairs.LOOK_ONCE_MORE_AFTER)
    assert repair.inspections == ROUNDS_UP_TO_THE_LOOK_ONCE_MORE
    assert "does not try again until something asks for a look" in caplog.text

    await repair.async_deactivate()


async def test_a_round_that_lands_gives_the_next_failure_its_look_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the one look once more is per failure, not once a lifetime."""
    repair = await _async_activate_and_look(hass, freezer)

    await _async_a_round_that_fails(hass, freezer, repair)
    await _async_move_on(hass, freezer, repairs.LOOK_ONCE_MORE_AFTER)
    assert repair.inspections == ROUNDS_UP_TO_THE_LOOK_ONCE_MORE

    # Days later, it fails again, and looks once more again.
    await _async_move_on(hass, freezer, timedelta(days=2))
    await _async_a_round_that_fails(hass, freezer, repair)
    assert repair.inspections == ROUNDS_UP_TO_THE_NEXT_FAILURE

    await _async_move_on(hass, freezer, repairs.LOOK_ONCE_MORE_AFTER)
    assert repair.inspections == ROUNDS_UP_TO_THE_NEXT_LOOK_ONCE_MORE

    await repair.async_deactivate()


async def test_a_look_asked_for_meanwhile_is_the_look_once_more(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a look something else asks for before the time is up counts.

    It looks the way it always does, and the one waiting is called off: one
    look after a failure, whoever asked for it.
    """
    repair = await _async_activate_and_look(hass, freezer)
    await _async_a_round_that_fails(hass, freezer, repair)

    repair.inspect_debouncer.async_schedule_call()
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == ROUNDS_UP_TO_THE_LOOK_ONCE_MORE

    await _async_move_on(hass, freezer, repairs.LOOK_ONCE_MORE_AFTER)
    assert repair.inspections == ROUNDS_UP_TO_THE_LOOK_ONCE_MORE

    await repair.async_deactivate()


async def test_deactivating_calls_off_the_look_once_more(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a repair deactivated after a failed round does not look again."""
    repair = await _async_activate_and_look(hass, freezer)
    await _async_a_round_that_fails(hass, freezer, repair)

    await repair.async_deactivate()

    # Called off, not left to find a debouncer that is shut down.
    assert not _timers_calling_back_into(hass, repair)

    await _async_move_on(hass, freezer, repairs.LOOK_ONCE_MORE_AFTER)
    assert repair.inspections == ROUNDS_UP_TO_THE_FAILURE


async def test_a_round_failing_after_deactivating_does_not_look_once_more(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a round that outlives its repair, and fails, leaves no timer."""
    halfway = asyncio.Event()
    carry_on = asyncio.Event()

    class _SlowStumblingRepair(MockStumblingRepair):
        async def async_inspect(self) -> None:
            halfway.set()
            await carry_on.wait()
            await super().async_inspect()

    repair = _SlowStumblingRepair(hass)
    repair.failures_to_come = 1
    await repair.async_activate()

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await halfway.wait()
    await repair.async_deactivate()
    carry_on.set()
    await hass.async_block_till_done()

    assert repair.inspections == 1
    assert not _timers_calling_back_into(hass, repair)


async def test_a_failed_round_names_the_repair(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the log says which repair failed, and where to report it."""
    repair = await _async_activate_and_look(hass, freezer)
    caplog.clear()

    await _async_a_round_that_fails(hass, freezer, repair)

    (record,) = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert record.name == "custom_components.spook"
    assert "Spook repair mock.mock_repair failed" in record.getMessage()
    assert "looks once more" in record.getMessage()
    assert "https://github.com/frenck/spook/issues" in record.getMessage()
    assert record.exc_info
    assert "Inspection went bump in the night" in caplog.text

    await repair.async_deactivate()


async def test_a_round_home_assistant_could_not_do_is_not_reported_as_broken(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a Home Assistant error is a warning, and still looked at once more.

    YAML that does not read is for its owner to fix, not something to report
    to Spook. The look once more is there all the same: fixed a minute later,
    it is seen a minute later.
    """
    repair = await _async_activate_and_look(hass, freezer)
    repair.fails_with = HomeAssistantError
    caplog.clear()

    await _async_a_round_that_fails(hass, freezer, repair)

    (record,) = [
        record
        for record in caplog.records
        if record.name == "custom_components.spook"
        and record.levelno >= logging.WARNING
    ]
    assert record.levelno == logging.WARNING
    assert record.getMessage() == (
        "Spook repair mock.mock_repair could not look and looks once more in "
        "60 seconds: Inspection went bump in the night"
    )
    assert not record.exc_info

    await _async_move_on(hass, freezer, repairs.LOOK_ONCE_MORE_AFTER)
    assert repair.inspections == ROUNDS_UP_TO_THE_LOOK_ONCE_MORE

    await repair.async_deactivate()


async def test_a_round_that_could_not_look_keeps_what_it_reported(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a repair that cannot judge anything is no repair that found it fine.

    Put right or not, it cannot tell, so what it reported stays up. Said at
    debug and no louder: some of these last as long as the installation does.
    And no look once more, which would only find the same.
    """
    repair = await _async_activate_and_look(hass, freezer)
    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one")
    caplog.clear()
    caplog.set_level(logging.DEBUG, logger="custom_components.spook")

    repair.current_issue_ids = set()
    repair.fails_with = repairs.CouldNotLook
    await _async_a_round_that_fails(hass, freezer, repair)
    assert repair.inspections == ROUNDS_UP_TO_THE_FAILURE

    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one")

    (record,) = [
        record
        for record in caplog.records
        if record.name == "custom_components.spook"
        and "could not look" in record.getMessage()
    ]
    assert record.levelno == logging.DEBUG
    assert record.getMessage() == (
        "Spook repair mock.mock_repair could not look, and keeps what it "
        "reported before: Inspection went bump in the night"
    )
    assert not [
        record
        for record in caplog.records
        if record.name == "custom_components.spook"
        and record.levelno >= logging.WARNING
    ]

    assert not _timers_calling_back_into(hass, repair)
    await _async_move_on(hass, freezer, repairs.LOOK_ONCE_MORE_AFTER)
    assert repair.inspections == ROUNDS_UP_TO_THE_FAILURE

    # The next look that can judge cleans up as usual.
    repair.inspect_debouncer.async_schedule_call()
    await _flush_debouncer(hass, freezer)
    assert repair.inspections == ROUNDS_UP_TO_THE_LOOK_ONCE_MORE

    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one") is None

    await repair.async_deactivate()


async def test_a_round_that_could_not_look_is_the_look_once_more(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a round that could not look, after one that failed, calls it off.

    It is the look the failure was waiting for, whoever asked for it. It did
    not land either, so a failure after it is the last word until a look
    does: no loop of looks once more.
    """
    repair = await _async_activate_and_look(hass, freezer)
    await _async_a_round_that_fails(hass, freezer, repair)
    assert _timers_calling_back_into(hass, repair)

    repair.fails_with = repairs.CouldNotLook
    await _async_a_round_that_fails(hass, freezer, repair)
    assert repair.inspections == ROUNDS_UP_TO_THE_LOOK_ONCE_MORE
    assert not _timers_calling_back_into(hass, repair)

    repair.fails_with = RuntimeError
    await _async_a_round_that_fails(hass, freezer, repair)
    assert repair.inspections == ROUNDS_UP_TO_THE_NEXT_FAILURE
    assert not _timers_calling_back_into(hass, repair)

    await _async_move_on(hass, freezer, repairs.LOOK_ONCE_MORE_AFTER)
    assert repair.inspections == ROUNDS_UP_TO_THE_NEXT_FAILURE

    await repair.async_deactivate()


async def test_how_each_look_went_is_written_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the last look is written down, for the diagnostics download.

    When it finished, and how it went. For a failure the type of the error
    and not its message, which can name an entity or a path.
    """
    repair = MockStumblingRepair(hass)
    assert repair.last_look is None

    await repair.async_activate()
    await _flush_debouncer(hass, freezer)
    assert repair.last_look == repairs.LastLook(
        dt_util.utcnow(), repairs.LookOutcome.FINE
    )

    await _async_a_round_that_fails(hass, freezer, repair)
    assert repair.last_look == repairs.LastLook(
        dt_util.utcnow(), repairs.LookOutcome.FAILED, "RuntimeError"
    )

    repair.fails_with = repairs.CouldNotLook
    await _async_a_round_that_fails(hass, freezer, repair)
    assert repair.last_look == repairs.LastLook(
        dt_util.utcnow(),
        repairs.LookOutcome.COULD_NOT_LOOK,
        "Inspection went bump in the night",
    )

    await repair.async_deactivate()


async def test_unloading_leaves_the_issue_registry_alone(
    hass: HomeAssistant,
) -> None:
    """Unloading happens on every reload, every update, every restart.

    Clearing the issues out here made all of those look like a fresh start,
    which is the whole of #1572.
    """
    repair = MockRepair(hass)
    await repair.async_activate()
    manager = repairs.SpookRepairManager(hass)
    manager._repairs.add(repair)
    manager.issue_registry.issues[(DOMAIN, "mock_repair_one")] = None
    manager.issue_registry.issues[(DOMAIN, "unrelated_issue")] = None

    await manager.async_on_unload()

    assert (DOMAIN, "mock_repair_one") in manager.issue_registry.issues
    assert (DOMAIN, "unrelated_issue") in manager.issue_registry.issues


async def test_an_ignored_repair_stays_ignored_through_a_reload(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Which is the reason the registry is left alone, spelled out.

    Pressing ignore writes that on the issue. Deleting the issue throws it
    away, and the next inspection puts the same problem back as something
    nobody has ever seen. Every reload, every update through HACS.
    """
    repair = MockRepair(hass)
    await repair.async_activate()
    repair.async_create_issue(issue_id="one", translation_placeholders={})

    ir.async_ignore_issue(hass, DOMAIN, "mock_repair_one", ignore=True)
    ignored = issue_registry.async_get_issue(DOMAIN, "mock_repair_one")
    assert ignored
    assert ignored.dismissed_version

    manager = repairs.SpookRepairManager(hass)
    manager._repairs.add(repair)
    await manager.async_on_unload()

    # Coming back up, and finding the same thing wrong all over again.
    await repair.async_activate()
    repair.async_create_issue(issue_id="one", translation_placeholders={})

    still = issue_registry.async_get_issue(DOMAIN, "mock_repair_one")
    assert still
    assert still.dismissed_version == ignored.dismissed_version

    await repair.async_deactivate()


class MockCleanupRepair(AbstractSpookRepair):
    """Mock repair with automatic issue cleanup."""

    domain = "mock"
    repair = "mock_repair"
    automatically_clean_up_issues = True

    inspected_ids: set[str] = set()
    current_issue_ids: set[str] = set()
    raise_on_inspect = False

    async def async_inspect(self) -> None:
        """Inspect the repair."""
        if self.raise_on_inspect:
            msg = "Inspection went bump in the night"
            raise HomeAssistantError(msg)
        self.possible_issue_ids.clear()
        self.possible_issue_ids.update(self.inspected_ids)
        for issue_id in self.current_issue_ids:
            self.async_create_issue(issue_id=issue_id)


async def test_cleanup_keeps_valid_issues(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test issues re-registered during an inspection are kept."""
    repair = MockCleanupRepair(hass)
    repair.inspected_ids = {"one"}
    repair.current_issue_ids = {"one"}

    await repair._async_inspect_with_cleanup()
    await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one")


async def test_cleanup_deletes_resolved_issues(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test issues are deleted when the inspected item no longer has one."""
    repair = MockCleanupRepair(hass)
    repair.inspected_ids = {"one"}
    repair.current_issue_ids = {"one"}

    await repair._async_inspect_with_cleanup()
    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one")

    repair.current_issue_ids = set()
    await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one") is None


async def test_cleanup_deletes_issues_for_removed_items(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test issues are deleted when their item is removed entirely."""
    repair = MockCleanupRepair(hass)
    repair.inspected_ids = {"one"}
    repair.current_issue_ids = {"one"}

    await repair._async_inspect_with_cleanup()
    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one")

    repair.inspected_ids = set()
    repair.current_issue_ids = set()
    await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one") is None


async def test_cleanup_deletes_stale_issues_for_inspected_items(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test stale issues from an earlier runtime are deleted.

    Issues persist in the issue registry across restarts, while the repair's
    in-memory bookkeeping starts empty. An inspected item without a current
    problem must have its leftover issue removed.
    """
    repairs.ir.async_create_issue(
        hass,
        domain=DOMAIN,
        issue_id="mock_repair_one",
        is_fixable=False,
        severity=repairs.ir.IssueSeverity.WARNING,
        translation_key="mock_repair",
    )

    repair = MockCleanupRepair(hass)
    repair.inspected_ids = {"one"}
    repair.current_issue_ids = set()

    await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one") is None


async def test_cleanup_survives_failing_inspection(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failing inspection keeps the cleanup bookkeeping intact.

    When an inspection raises, the previously registered issue IDs must be
    restored so the next successful inspection can still clean up issues
    for items that were resolved or removed in the meantime.
    """
    repair = MockCleanupRepair(hass)
    repair.inspected_ids = {"one"}
    repair.current_issue_ids = {"one"}

    await repair._async_inspect_with_cleanup()
    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one")

    # Logged by the repair itself, so it no longer raises.
    repair.raise_on_inspect = True
    await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one")
    assert repair.issue_ids == {"one"}

    repair.raise_on_inspect = False
    repair.inspected_ids = set()
    repair.current_issue_ids = set()
    await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_one") is None


async def test_cleanup_deletes_stale_issues_for_items_removed_before_restart(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test stale issues for items removed while Home Assistant was down.

    Issues persist in the issue registry across restarts. An issue whose
    item no longer exists at all is never inspected again, so cleanup must
    consider the persisted issues of this repair as candidates too.
    """
    repairs.ir.async_create_issue(
        hass,
        domain=DOMAIN,
        issue_id="mock_repair_gone",
        is_fixable=False,
        severity=repairs.ir.IssueSeverity.WARNING,
        translation_key="mock_repair",
    )

    repair = MockCleanupRepair(hass)
    repair.inspected_ids = set()
    repair.current_issue_ids = set()

    await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, "mock_repair_gone") is None


class MockFindingsRepair(AbstractSpookRepair):
    """Mock repair that reports a set of findings in one place."""

    domain = "mock"
    repair = "mock_repair"
    automatically_clean_up_issues = True

    findings: set[str] = set()

    async def async_inspect(self) -> None:
        """Report whatever is currently broken in the one place there is."""
        if self.findings:
            self.async_create_issue(
                issue_id="script.haunted",
                references=self.findings,
                translation_placeholders={"entities": ", ".join(sorted(self.findings))},
            )


def _the_one_issue(issue_registry: ir.IssueRegistry) -> ir.IssueEntry:
    """Return the single issue this repair left, and insist there is one."""
    issues = [
        entry
        for (domain, _issue_id), entry in issue_registry.issues.items()
        if domain == DOMAIN
    ]

    assert len(issues) == 1, f"expected one issue, found {len(issues)}"

    return issues[0]


async def test_the_same_findings_keep_the_same_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a finding that has not changed is not reported anew.

    Otherwise every inspection would throw away what somebody decided about
    it, and a repair inspects on every reload.
    """
    repair = MockFindingsRepair(hass)
    repair.findings = {"light.ghost"}

    await repair._async_inspect_with_cleanup()
    first = _the_one_issue(issue_registry).issue_id

    await repair._async_inspect_with_cleanup()

    assert _the_one_issue(issue_registry).issue_id == first


async def test_ignoring_one_finding_does_not_hide_the_next(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a dismissal covers what was dismissed, and nothing after it.

    An issue used to be keyed to the place its findings were in, so pressing
    ignore meant "nothing here, ever". Home Assistant keeps the dismissal
    against that ID while the text is rewritten underneath, so the next
    genuinely broken thing in the same script arrived already silenced by a
    decision somebody made about something else. #1395.
    """
    repair = MockFindingsRepair(hass)
    repair.findings = {"zha.issue_zigbee_cluster_command"}

    await repair._async_inspect_with_cleanup()
    ignored = _the_one_issue(issue_registry)
    ir.async_ignore_issue(hass, DOMAIN, ignored.issue_id, ignore=True)
    assert issue_registry.async_get_issue(DOMAIN, ignored.issue_id).dismissed_version

    # Something else in the same script breaks, and this one is real.
    repair.findings = {"light.actually_gone"}
    await repair._async_inspect_with_cleanup()

    now = _the_one_issue(issue_registry)

    assert now.issue_id != ignored.issue_id
    assert not now.dismissed_version


async def test_findings_that_change_leave_nothing_behind(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue for a superseded set of findings is cleaned up.

    An ID that follows the findings means a new one every time they move, and
    without the cleanup behind it that is a pile of issues about the same
    script rather than one.
    """
    repair = MockFindingsRepair(hass)

    for findings in ({"light.one"}, {"light.one", "light.two"}, {"light.three"}):
        repair.findings = findings
        await repair._async_inspect_with_cleanup()

        assert _the_one_issue(issue_registry)


async def test_findings_in_a_different_order_are_the_same_findings(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the order references arrive in does not move the issue.

    They come out of sets and walks of a configuration, so the order is not
    anything anybody chose. An ID that followed it would resurface an issue
    somebody had already dealt with, at random.
    """
    repair = MockFindingsRepair(hass)

    repair.findings = {"light.a", "light.b", "light.c"}
    await repair._async_inspect_with_cleanup()
    first = _the_one_issue(issue_registry).issue_id

    repair.findings = {"light.c", "light.a", "light.b"}
    await repair._async_inspect_with_cleanup()

    assert _the_one_issue(issue_registry).issue_id == first


async def test_findings_from_before_a_restart_are_cleaned_up_from_the_registry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an issue keyed to its findings goes without `possible_issue_ids`.

    Its ID is the owner with a fingerprint on the end, so the bare owner a
    repair used to put in `possible_issue_ids` never named it. A repair
    starting after a restart remembers nothing of its own, and what the
    earlier one left is found in the issue registry: gone when the finding
    is, and replaced when it changed.
    """
    before_the_restart = MockFindingsRepair(hass)
    before_the_restart.findings = {"light.ghost"}
    await before_the_restart._async_inspect_with_cleanup()
    left_behind = _the_one_issue(issue_registry).issue_id

    changed = MockFindingsRepair(hass)
    changed.findings = {"light.another_ghost"}
    await changed._async_inspect_with_cleanup()

    assert not changed.possible_issue_ids
    assert _the_one_issue(issue_registry).issue_id != left_behind
    left_behind = _the_one_issue(issue_registry).issue_id

    gone = MockFindingsRepair(hass)
    gone.findings = set()
    await gone._async_inspect_with_cleanup()

    assert not gone.possible_issue_ids
    assert issue_registry.async_get_issue(DOMAIN, left_behind) is None
    assert not [
        entry
        for (domain, _issue_id), entry in issue_registry.issues.items()
        if domain == DOMAIN
    ]


class MockComponentRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Mock repair over an entity component, the way the real ones work."""

    domain = "mock"
    repair = "mock_repair"
    entity_label = "automation"
    reference_label = "entities"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    unknown: set[str] = set()

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return whatever is currently broken."""
        del entity
        return set(self.unknown)


async def test_an_issue_goes_once_the_entity_is_put_right(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fixing the references clears the issue that reported them.

    Worth pinning on the real base rather than a stand-in. This repair used
    to list every entity it inspected in ``possible_issue_ids`` so the
    cleanup could reach them, and an ID that follows the findings is not in
    that list any more. What the repair left behind is read back out of the
    issue registry instead, and this is the test that says so.
    """
    hass.data.setdefault(DATA_INSTANCES, {})["mock"] = SimpleNamespace(
        entities=[
            SimpleNamespace(
                entity_id="automation.haunted",
                name="Haunted",
                unique_id="haunted",
            )
        ],
    )

    repair = MockComponentRepair(hass)
    repair.unknown = {"light.ghost"}
    await repair._async_inspect_with_cleanup()

    assert _the_one_issue(issue_registry)

    # Somebody fixes the automation.
    repair.unknown = set()
    await repair._async_inspect_with_cleanup()

    assert not [
        entry
        for (domain, _issue_id), entry in issue_registry.issues.items()
        if domain == DOMAIN
    ]


async def test_findings_that_run_together_are_told_apart(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a reference cannot borrow the one next to it.

    The digest used to be taken over the references run together with a
    separator between them, which reads two different sets the same way when
    a reference holds that separator itself. Entity IDs cannot, but resource
    URLs, notifier names and customize keys are whatever somebody typed, and
    the cost of getting it wrong is a dismissal covering a finding nobody
    dismissed.
    """
    repair = MockFindingsRepair(hass)

    repair.findings = {"light.a\nlight.b", "light.c"}
    await repair._async_inspect_with_cleanup()
    first = _the_one_issue(issue_registry).issue_id

    repair.findings = {"light.a", "light.b\nlight.c"}
    await repair._async_inspect_with_cleanup()

    assert _the_one_issue(issue_registry).issue_id != first


async def test_a_look_still_running_when_deactivated_leaves_the_registry_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an inspection that outlives its repair neither raises nor clears.

    Shutting the debouncer down stops the next look, not one already under
    way. That one carried on after Spook was disabled or reloaded, filing
    what it found and clearing what it did not, which after a reload can be
    the fresh issues of the repair that replaced it.
    """
    halfway = asyncio.Event()
    carry_on = asyncio.Event()

    class _SlowRepair(MockFindingsRepair):
        async def async_inspect(self) -> None:
            halfway.set()
            await carry_on.wait()
            await super().async_inspect()

    ir.async_create_issue(
        hass,
        DOMAIN,
        "mock_repair_left_by_the_new_one",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="mock_repair",
    )
    repair = _SlowRepair(hass)
    repair.findings = {"light.ghost"}
    await repair.async_activate()

    looking = hass.async_create_task(repair._async_inspect_with_cleanup())
    await halfway.wait()
    await repair.async_deactivate()
    carry_on.set()
    await looking

    assert [
        issue_id for (domain, issue_id) in issue_registry.issues if domain == DOMAIN
    ] == ["mock_repair_left_by_the_new_one"]
