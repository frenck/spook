"""Shared helpers for testing Spook repairs."""

# pylint: disable=protected-access
from __future__ import annotations

import re
from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.const import EVENT_STATE_CHANGED

from custom_components.spook.const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers import issue_registry as ir

    from custom_components.spook.repairs import AbstractSpookRepair


def async_issue_about(
    issue_registry: ir.IssueRegistry,
    issue_id: str,
) -> ir.IssueEntry | None:
    """Return the issue a repair raised in one place, whatever it found there.

    An issue ID ends in a digest of the findings, so a test cannot spell the
    whole of it out. Writing the digest in would pin a hash rather than a
    behaviour, and would have to be worked out again every time the fixture
    moved. Pass the part that names the place instead.

    Raises if a repair left more than one issue there, which would mean the
    previous round's findings were never cleaned up.
    """
    keyed_to_findings = re.compile(rf"{re.escape(issue_id)}_[0-9a-f]{{8}}\Z")
    found = [
        entry
        for (domain, candidate), entry in issue_registry.issues.items()
        if domain == DOMAIN and keyed_to_findings.fullmatch(candidate)
    ]

    if not found:
        return None

    if len(found) > 1:
        message = f"{len(found)} issues about {issue_id}, expected one"
        raise AssertionError(message)

    return found[0]


async def async_count_scheduled_inspections(
    hass: HomeAssistant,
    repair: AbstractSpookRepair,
    entity_id: str,
    old_state: State | None,
    new_state: State | None,
) -> int:
    """Return how many inspections one state change schedules on a repair.

    Takes a repair that is already activated, and inspected if its listener
    needs to know something an inspection works out. Swaps the debouncer for
    a counter so the scheduling is observed rather than the inspection.
    """
    repair.inspect_debouncer.async_shutdown()
    calls = 0

    def async_schedule_call() -> None:
        """Capture scheduled inspections."""
        nonlocal calls
        calls += 1

    repair.inspect_debouncer = SimpleNamespace(
        async_schedule_call=async_schedule_call,
        async_shutdown=lambda: None,
    )

    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {"entity_id": entity_id, "old_state": old_state, "new_state": new_state},
    )
    await hass.async_block_till_done()

    await repair.async_deactivate()
    return calls
