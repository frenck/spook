"""Tests for event loop yielding during repair inspections."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.entity_component import DATA_INSTANCES

from custom_components.spook import repairs, template_extraction
from custom_components.spook.repairs import (
    AbstractSpookEntityComponentUnknownReferencesRepair,
    AbstractSpookRepair,
)
from custom_components.spook.template_extraction import (
    async_extract_entities_from_config,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    import pytest

ENTITY_COUNT = 120
EXPECTED_YIELDS = 2  # After entity 50 and entity 100.


class _UnavailableEntity:  # pylint: disable=too-few-public-methods
    """Marker class for unavailable entities."""


class _ReferencesRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Mock unknown-references repair."""

    domain = "automation"
    repair = "mock_repair"
    unavailable_entity_class = _UnavailableEntity
    entity_label = "automation"
    reference_label = "entities"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return no unknown references."""
        del entity
        return set()


def _count_sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record asyncio.sleep calls made during the test."""
    calls: list[float] = []
    original_sleep = asyncio.sleep

    async def _counting_sleep(delay: float, result: object = None) -> object:
        calls.append(delay)
        return await original_sleep(delay, result)

    monkeypatch.setattr(asyncio, "sleep", _counting_sleep)
    return calls


async def test_component_inspection_yields_to_event_loop(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the entity component inspection yields periodically."""
    entities = [
        SimpleNamespace(entity_id=f"automation.spooky_{index}")
        for index in range(ENTITY_COUNT)
    ]
    hass.data.setdefault(DATA_INSTANCES, {})["automation"] = SimpleNamespace(
        entities=entities,
    )

    # Only the count is under test here; a slow machine would otherwise add
    # turns given by the clock.
    monkeypatch.setattr(repairs, "YIELD_AFTER", float("inf"))
    repair = _ReferencesRepair(hass)
    calls = _count_sleeps(monkeypatch)

    await repair.async_inspect()

    assert calls == [0] * EXPECTED_YIELDS


async def test_component_inspection_yields_by_the_clock(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The inspection hands the loop back once its time is up, at any count.

    Fewer entities than one count interval, so every turn comes from the
    clock. A time limit that is always exceeded gives one turn per entity.
    #2005.
    """
    entities = [
        SimpleNamespace(entity_id=f"automation.spooky_{index}") for index in range(5)
    ]
    hass.data.setdefault(DATA_INSTANCES, {})["automation"] = SimpleNamespace(
        entities=entities,
    )
    monkeypatch.setattr(repairs, "YIELD_AFTER", -1.0)
    calls = _count_sleeps(monkeypatch)

    await _ReferencesRepair(hass).async_inspect()

    assert calls == [0] * len(entities)


async def test_reading_the_templates_of_a_configuration_yields_by_the_clock(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reading a configuration's templates hands the loop back by the clock.

    Without a time limit nothing in there waits for anything; with one that
    is always exceeded, there is a turn before every template. What is found
    stays the same either way. #2005.
    """
    config = {
        "first": "{{ states('sensor.one') }}",
        "second": "{{ states('sensor.two') }}",
        "third": "{{ states('sensor.three') }}",
    }
    expected = {"sensor.one", "sensor.two", "sensor.three"}
    calls = _count_sleeps(monkeypatch)

    monkeypatch.setattr(template_extraction, "YIELD_AFTER", float("inf"))
    assert await async_extract_entities_from_config(hass, config, set()) == expected
    assert not calls

    monkeypatch.setattr(template_extraction, "YIELD_AFTER", -1.0)
    assert await async_extract_entities_from_config(hass, config, set()) == expected
    assert calls == [0] * len(config)


async def test_an_entity_arriving_mid_inspection_does_not_kill_the_round(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The inspection hands the event loop a turn every fifty entities.

    Home Assistant is free to load or remove an automation during one of those
    turns, and the collection behind `component.entities` is the live one. Core
    says as much: "callers that iterate over this asynchronously should make a
    copy". Iterating it directly raised `RuntimeError: dictionary changed size
    during iteration`, which nothing above catches, so one badly timed reload
    took out the whole round rather than one entity. Reported as #1558.
    """
    live = {
        f"automation.spooky_{index}": SimpleNamespace(
            entity_id=f"automation.spooky_{index}"
        )
        for index in range(ENTITY_COUNT)
    }

    class _LiveComponent:  # pylint: disable=too-few-public-methods
        """Stands in for `EntityComponent`, whose `entities` is a live view."""

        @property
        def entities(self) -> Any:
            """Return the live view, not a copy of it."""
            return live.values()

    hass.data.setdefault(DATA_INSTANCES, {})["automation"] = _LiveComponent()

    # An automation loads the first time the inspection gives up control.
    original_sleep = asyncio.sleep
    added = False

    async def _sleep_and_add(delay: float, result: object = None) -> object:
        nonlocal added
        if not added:
            added = True
            live["automation.arrived_late"] = SimpleNamespace(
                entity_id="automation.arrived_late"
            )
        return await original_sleep(delay, result)

    monkeypatch.setattr(asyncio, "sleep", _sleep_and_add)

    await _ReferencesRepair(hass).async_inspect()

    assert added, "the inspection never yielded, so nothing was tested"


class _TurnTakingRepair(AbstractSpookRepair):
    """Mock repair writing down when its inspection starts and ends."""

    domain = "mock"
    repair = "mock_repair"

    def __init__(self, hass: HomeAssistant, name: str, log: list[str]) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self.name = name
        self.log = log

    async def async_inspect(self) -> None:
        """Inspect in a few slices, handing the loop back in between."""
        self.log.append(f"{self.name} starts")
        for _ in range(3):
            await asyncio.sleep(0)
        self.log.append(f"{self.name} ends")


async def test_inspections_take_turns(hass: HomeAssistant) -> None:
    """Test rounds started together run one after the other.

    Side by side, every hand-back went to the next round instead of to Home
    Assistant, and the loop was only free once all of them had their slice.
    """
    log: list[str] = []
    first = _TurnTakingRepair(hass, "first", log)
    second = _TurnTakingRepair(hass, "second", log)

    await asyncio.gather(
        first._async_inspect_with_cleanup(),
        second._async_inspect_with_cleanup(),
    )

    assert log == ["first starts", "first ends", "second starts", "second ends"]


async def test_a_repair_unloaded_while_waiting_its_turn_does_not_look(
    hass: HomeAssistant,
) -> None:
    """Test a round waiting for its turn is dropped once its repair is gone."""
    log: list[str] = []
    first = _TurnTakingRepair(hass, "first", log)
    unloaded = _TurnTakingRepair(hass, "unloaded", log)
    await unloaded.async_activate()

    first_round = asyncio.create_task(first._async_inspect_with_cleanup())
    waiting_round = asyncio.create_task(unloaded._async_inspect_with_cleanup())
    await asyncio.sleep(0)
    await unloaded.async_deactivate()
    await asyncio.gather(first_round, waiting_round, return_exceptions=True)

    assert log == ["first starts", "first ends"]

    # Not left waiting until the turn comes: deactivating called it off.
    assert waiting_round.cancelled()
