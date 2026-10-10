"""Tests for Spook repair cleanup."""
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order

from __future__ import annotations

import asyncio

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_component import DATA_INSTANCES

from custom_components.spook import repairs
from custom_components.spook.const import DOMAIN
from custom_components.spook.repairs import (
    AbstractSpookEntityComponentUnknownReferencesRepair,
    AbstractSpookRepair,
    AbstractSpookRepairBase,
)
import pytest

EXPECTED_UNSUBSCRIBE_COUNT = 4
EXPECTED_INTERVAL_INSPECTIONS = 2

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.config_entries import ConfigEntry, ConfigEntryChange
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

    repair.raise_on_inspect = True
    with pytest.raises(HomeAssistantError):
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
