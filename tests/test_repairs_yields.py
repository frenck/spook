"""Tests for event loop yielding during repair inspections."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM

from custom_components.spook.repairs import (
    AbstractSpookEntityComponentUnknownReferencesRepair,
    AbstractSpookEntityPlatformUnknownSourceRepair,
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


class _SourceRepair(AbstractSpookEntityPlatformUnknownSourceRepair):
    """Mock unknown-source repair."""

    domain = "integration"
    repair = "mock_repair"

    def _get_source_entity_id(self, entity: Any) -> str:
        """Return a source entity ID that is always known."""
        del entity
        return "sensor.time"


def _count_sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record asyncio.sleep calls made during the test."""
    calls: list[float] = []
    original_sleep = asyncio.sleep

    async def _counting_sleep(delay: float) -> None:
        calls.append(delay)
        await original_sleep(delay)

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

    repair = _ReferencesRepair(hass)
    calls = _count_sleeps(monkeypatch)

    await repair.async_inspect()

    assert calls == [0] * EXPECTED_YIELDS


async def test_platform_inspection_yields_to_event_loop(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the entity platform inspection yields periodically."""
    platform = SimpleNamespace(
        domain="sensor",
        entities={
            f"sensor.spooky_{index}": SimpleNamespace(
                entity_id=f"sensor.spooky_{index}",
            )
            for index in range(ENTITY_COUNT)
        },
    )
    hass.data.setdefault(DATA_ENTITY_PLATFORM, {})["integration"] = [platform]

    repair = _SourceRepair(hass)
    calls = _count_sleeps(monkeypatch)

    await repair.async_inspect()

    assert calls == [0] * EXPECTED_YIELDS
