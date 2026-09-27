"""Tests for how an inspection works out its rename suggestions.

Describing a broken entity reference means comparing it against every entity
in its domain, and a house with a lot of broken references has a lot of them
to compare. Done inline, one issue description at a time, that was tens of
seconds during which Home Assistant did nothing else; #1667.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.entity_component import DATA_INSTANCES

from custom_components.spook import entity_suggestions
from custom_components.spook.repairs import (
    AbstractSpookEntityComponentUnknownReferencesRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir
    import pytest

ENTITY_COUNT = 30


class _BrokenReferencesRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Repair where every inspected entity has a broken reference of its own."""

    domain = "automation"
    repair = "mock_repair"
    entity_label = "automation"
    reference_label = "entities"
    references_are_entities = True
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return a missing entity of this entity's own, as a real house has."""
        return {f"sensor.living_room_temperatur_{entity.unique_id}"}


def _stock_entities(hass: HomeAssistant) -> None:
    """Register the automations to inspect, plus something to suggest."""
    hass.data.setdefault(DATA_INSTANCES, {})["automation"] = SimpleNamespace(
        entities=[
            SimpleNamespace(
                entity_id=f"automation.spooky_{index}",
                name=f"Spooky {index}",
                unique_id=f"spooky_{index}",
            )
            for index in range(ENTITY_COUNT)
        ],
    )
    hass.states.async_set("sensor.living_room_temperature", "21")


async def test_nothing_is_described_until_the_walk_is_done(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the round gathers every finding before describing any of them.

    That is what lets the comparing go to a thread in one hop instead of
    landing on the event loop once per issue.
    """
    _stock_entities(hass)

    timeline: list[str] = []
    original = entity_suggestions.difflib.get_close_matches

    def _recording(word: str, *args: object, **kwargs: object) -> list[str]:
        timeline.append("compare")
        return original(word, *args, **kwargs)

    monkeypatch.setattr(entity_suggestions.difflib, "get_close_matches", _recording)

    class _Watched(_BrokenReferencesRepair):
        """The same repair, saying when it looks at an entity."""

        async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
            """Note the visit, then answer as usual."""
            timeline.append("walk")
            return await super()._async_compute_unknown_references(entity)

    await _Watched(hass).async_inspect()

    assert timeline == ["walk"] * ENTITY_COUNT + ["compare"] * ENTITY_COUNT


async def test_the_comparing_happens_off_the_event_loop(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the fuzzy matching runs in a thread, not on the event loop.

    This is the whole point of gathering the round's findings before
    describing any of them. Home Assistant has to stay answerable while Spook
    is working out what somebody meant to type.
    """
    _stock_entities(hass)

    threads: list[str] = []
    original = entity_suggestions.difflib.get_close_matches

    def _recording(*args: object, **kwargs: object) -> list[str]:
        threads.append(threading.current_thread().name)
        return original(*args, **kwargs)

    monkeypatch.setattr(entity_suggestions.difflib, "get_close_matches", _recording)

    await _BrokenReferencesRepair(hass).async_inspect()

    assert threads, "nothing was compared, so nothing was tested"
    assert threading.main_thread().name not in threads


async def test_every_finding_still_gets_its_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test collecting the findings first does not lose any of them."""
    _stock_entities(hass)

    await _BrokenReferencesRepair(hass).async_inspect()

    issues = [
        issue_id
        for domain, issue_id in issue_registry.issues
        if domain == "spook" and issue_id.startswith("mock_repair_")
    ]

    assert len(issues) == ENTITY_COUNT
