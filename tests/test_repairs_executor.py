"""Tests for unknown-references computations running in the executor."""

# ruff: noqa: SLF001
# pylint: disable=protected-access

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.automation.repairs.unknown_entity_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir
    import pytest


async def test_unknown_references_are_computed_in_the_executor(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a round's computation runs off the event loop, findings intact.

    Walking a configuration and reading its templates is the expensive
    part of an inspection, and it is pure computation over plain data.
    It runs in the executor, from snapshots taken on the event loop, so
    a big house cannot stall everything else while Spook looks.
    """
    loop_thread = threading.get_ident()
    ran_on: list[int] = []
    real_compute = SpookRepair._compute_unknown_references

    def _spying_compute(repair: SpookRepair, entity: Any) -> set[str]:
        ran_on.append(threading.get_ident())
        return real_compute(repair, entity)

    monkeypatch.setattr(SpookRepair, "_compute_unknown_references", _spying_compute)

    hass.services.async_register("light", "turn_on", lambda _call: None)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "garage",
                "alias": "garage",
                "triggers": [{"trigger": "event", "event_type": "arrived"}],
                "actions": [
                    {
                        "action": "light.turn_on",
                        "target": {"entity_id": "light.ghost"},
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    await SpookRepair(hass).async_inspect()

    assert ran_on
    assert all(thread != loop_thread for thread in ran_on)

    issue = async_issue_about(
        issue_registry, "automation_unknown_entity_references_automation.garage"
    )
    assert issue
    assert issue.translation_placeholders is not None
    assert "light.ghost" in issue.translation_placeholders["entities"]
