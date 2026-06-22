"""Tests for Spook repair cleanup."""
# ruff: noqa: SLF001
# pylint: disable=protected-access

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.spook import repairs
from custom_components.spook.repairs import AbstractSpookRepair, AbstractSpookRepairBase

EXPECTED_UNSUBSCRIBE_COUNT = 3

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry, ConfigEntryChange
    from homeassistant.core import HomeAssistant
    import pytest


class MockRepairBase(AbstractSpookRepairBase):
    """Mock base repair."""

    domain = "mock"
    repair = "mock_repair"

    async def async_activate(self) -> None:
        """Activate the repair."""

    async def async_inspect(self) -> None:
        """Inspect the repair."""


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
