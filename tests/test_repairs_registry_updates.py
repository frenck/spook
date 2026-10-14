"""Tests for which entity registry updates have a repair look again."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.helpers import entity_registry as er

from custom_components.spook.repairs import AbstractSpookRepair
import pytest

# The first look on activating, then one per update worth looking at.
ONE_MORE_LOOK = 2
TWO_MORE_LOOKS = 3

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant


class _RegistryRepair(AbstractSpookRepair):
    """Repair that looks again on every entity registry update it is told of."""

    domain = "mock"
    repair = "mock_repair"
    inspect_events = {er.EVENT_ENTITY_REGISTRY_UPDATED}

    inspections = 0

    async def async_inspect(self) -> None:
        """Count the inspection."""
        self.inspections += 1


async def _settle(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the inspection debouncer run whatever it has waiting."""
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _activated(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> tuple[_RegistryRepair, er.RegistryEntry]:
    """Return an activated repair past its first look, and an entity."""
    entry = entity_registry.async_get_or_create(
        "media_player",
        "androidtv",
        "living_room",
        capabilities={"source_list": ["HDMI 1"]},
        supported_features=1,
    )
    repair = _RegistryRepair(hass)
    await repair.async_activate()
    await _settle(hass, freezer)
    assert repair.inspections == 1
    return repair, entry


@pytest.mark.parametrize(
    "changes",
    [
        {"capabilities": {"source_list": ["HDMI 1", "HDMI 2"]}},
        {"supported_features": 2},
        {"capabilities": {"source_list": ["HDMI 2"]}, "supported_features": 3},
    ],
)
async def test_what_no_repair_looks_at_is_let_go(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    changes: dict[str, Any],
) -> None:
    """A media player's sources changing names nothing, and goes unlooked at.

    Integrations write these all day long, and every one of them had every
    repair listening to the registry go through the whole house again.
    """
    repair, entry = await _activated(hass, freezer, entity_registry)

    entity_registry.async_update_entity(entry.entity_id, **changes)
    await _settle(hass, freezer)

    assert repair.inspections == 1
    await repair.async_deactivate()


@pytest.mark.parametrize(
    "changes",
    [
        {"new_entity_id": "media_player.lounge"},
        {"name": "Lounge"},
        {"icon": "mdi:television"},
        {"disabled_by": er.RegistryEntryDisabler.USER},
        {"capabilities": {"source_list": ["HDMI 2"]}, "name": "Lounge"},
    ],
)
async def test_anything_else_written_is_looked_at(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    changes: dict[str, Any],
) -> None:
    """Anything more than that, even alongside it, is looked at again."""
    repair, entry = await _activated(hass, freezer, entity_registry)

    entity_registry.async_update_entity(entry.entity_id, **changes)
    await _settle(hass, freezer)

    assert repair.inspections == ONE_MORE_LOOK
    await repair.async_deactivate()


async def test_entities_coming_and_going_are_looked_at(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """An entity registered or removed is always worth another look."""
    repair, entry = await _activated(hass, freezer, entity_registry)

    entity_registry.async_get_or_create("select", "mqtt", "input")
    await _settle(hass, freezer)
    assert repair.inspections == ONE_MORE_LOOK

    entity_registry.async_remove(entry.entity_id)
    await _settle(hass, freezer)
    assert repair.inspections == TWO_MORE_LOOKS

    await repair.async_deactivate()
