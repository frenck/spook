"""Shared helpers for testing Spook repairs."""

# pylint: disable=protected-access
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.const import EVENT_STATE_CHANGED

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

    from custom_components.spook.repairs import AbstractSpookRepair


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
