"""Tests for Spook repair cleanup."""
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError

from custom_components.spook import repairs
from custom_components.spook.const import DOMAIN
from custom_components.spook.repairs import AbstractSpookRepair, AbstractSpookRepairBase
import pytest

EXPECTED_UNSUBSCRIBE_COUNT = 3

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry, ConfigEntryChange
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


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

    inspections = 0

    async def async_inspect(self) -> None:
        """Inspect the repair."""
        self.inspections += 1


async def test_deactivate_deletes_issues_from_snapshot(hass: HomeAssistant) -> None:
    """Test deactivation can delete issues while mutating the issue ID set."""
    repair = MockRepairBase(hass)
    repair.issue_ids = {"one", "two"}

    await repair.async_deactivate()

    assert not repair.issue_ids


async def test_deactivate_keeps_issues_registered_when_stopping(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test shutdown keeps issues for the issue registry to restore."""
    deleted: list[tuple[str, str]] = []

    def async_delete_issue(
        _hass: HomeAssistant,
        domain: str,
        issue_id: str,
    ) -> None:
        """Capture deleted issues."""
        deleted.append((domain, issue_id))

    monkeypatch.setattr(repairs.ir, "async_delete_issue", async_delete_issue)
    monkeypatch.setattr(hass, "is_stopping", True)

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


async def test_repair_manager_removes_issues_on_unload(hass: HomeAssistant) -> None:
    """Test unloading removes issues created by the repair."""
    repair = MockRepair(hass)
    await repair.async_activate()
    manager = repairs.SpookRepairManager(hass)
    manager._repairs.add(repair)
    manager.issue_registry.issues[(DOMAIN, "mock_mock_repair_one")] = None
    manager.issue_registry.issues[(DOMAIN, "unrelated_issue")] = None

    await manager.async_on_unload()

    assert (DOMAIN, "mock_mock_repair_one") not in manager.issue_registry.issues
    assert (DOMAIN, "unrelated_issue") in manager.issue_registry.issues


async def test_repair_manager_keeps_issues_on_shutdown(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test shutdown keeps issues for the issue registry to restore."""
    repair = MockRepair(hass)
    await repair.async_activate()
    manager = repairs.SpookRepairManager(hass)
    manager._repairs.add(repair)
    manager.issue_registry.issues[(DOMAIN, "mock_mock_repair_one")] = None
    monkeypatch.setattr(hass, "is_stopping", True)

    await manager.async_on_unload()

    assert (DOMAIN, "mock_mock_repair_one") in manager.issue_registry.issues


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
