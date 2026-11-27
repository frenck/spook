"""Tests for repairs hearing an entity arrive that they reported as unknown.

Plenty of entities never touch the entity registry. A YAML sensor without a
unique ID, a zone from YAML, a device tracker from `known_devices.yaml`:
each arrives as a state and nothing else, often well after Home Assistant
started. A repair that reported one as unknown has to hear it arrive, or
its issue outlives its cause until something else brings a look.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from pytest_homeassistant.common import MockConfigEntry
import pytest

from homeassistant.helpers import area_registry as ar, issue_registry as ir

from custom_components.spook.entity_filtering import (
    async_setup_all_entity_ids_cache_invalidation,
)

from tests.ectoplasms.proximity.repairs.conftest import async_set_up_proximity
from tests.repair_helpers import async_issue_about, async_wait_out_the_repair

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

    from custom_components.spook.repairs import AbstractSpookRepair


async def _helper(hass: HomeAssistant) -> str:
    """Set up a helper whose source is not there yet."""
    entry = MockConfigEntry(
        domain="derivative",
        title="Late",
        options={"name": "Late", "source": "sensor.late"},
    )
    entry.add_to_hass(hass)
    return entry.entry_id


async def _min_max(hass: HomeAssistant) -> str:
    """Set up a min/max helper with one member not there yet."""
    hass.states.async_set("sensor.one", "1")
    hass.states.async_set("sensor.two", "2")
    entry = MockConfigEntry(
        domain="min_max",
        title="Late",
        options={"entity_ids": ["sensor.one", "sensor.two", "sensor.late"]},
    )
    entry.add_to_hass(hass)
    return entry.entry_id


async def _proximity_zone(hass: HomeAssistant) -> str:
    """Set up proximity watching a zone that is not there yet."""
    return (await async_set_up_proximity(hass, zone="zone.late")).entry_id


async def _proximity_ignored_zone(hass: HomeAssistant) -> str:
    """Set up proximity ignoring a zone that is not there yet."""
    return (await async_set_up_proximity(hass, ignored_zones=["zone.late"])).entry_id


async def _proximity_tracked(hass: HomeAssistant) -> str:
    """Set up proximity tracking a person that is not there yet."""
    return (await async_set_up_proximity(hass, tracked=["person.late"])).entry_id


async def _area(hass: HomeAssistant) -> str:
    """Set up an area whose temperature sensor is not there right now.

    Home Assistant only takes a sensor that is there when it is picked.
    """
    hass.states.async_set("sensor.late", "20", {"device_class": "temperature"})
    area_registry = ar.async_get(hass)
    area = area_registry.async_create("Kitchen")
    area_registry.async_update(area.id, temperature_entity_id="sensor.late")
    hass.states.async_remove("sensor.late")
    return area.id


async def _async_look(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the repair take the look it was asked for, and finish it.

    The look the wait lets loose can still be on its way to its turn when
    the wait ends, so this waits for Home Assistant to be done as well.
    Nothing here is slow on purpose, so that is soon.
    """
    await async_wait_out_the_repair(hass, freezer)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("module", "set_up", "entity_id"),
    [
        (
            "homeassistant.repairs.unknown_helper_source_references",
            _helper,
            "sensor.late",
        ),
        ("homeassistant.repairs.min_max_unknown_sources", _min_max, "sensor.late"),
        ("proximity.repairs.unknown_zone", _proximity_zone, "zone.late"),
        (
            "proximity.repairs.unknown_ignored_zones",
            _proximity_ignored_zone,
            "zone.late",
        ),
        (
            "proximity.repairs.unknown_tracked_entities",
            _proximity_tracked,
            "person.late",
        ),
        ("homeassistant.repairs.unknown_area_sensors", _area, "sensor.late"),
    ],
)
async def test_an_entity_arriving_clears_its_issue(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    module: str,
    set_up: Callable[[HomeAssistant], Awaitable[str]],
    entity_id: str,
) -> None:
    """Test an entity that arrives as a state takes its issue along."""
    async_setup_all_entity_ids_cache_invalidation(hass)
    place = await set_up(hass)
    repair: AbstractSpookRepair = import_module(
        f"custom_components.spook.ectoplasms.{module}"
    ).SpookRepair(hass)
    issue_id = f"{repair.repair}_{place}"
    issue_registry = ir.async_get(hass)

    await repair.async_activate()
    await _async_look(hass, freezer)
    reported = async_issue_about(issue_registry, issue_id)

    hass.states.async_set(entity_id, "0", {"device_class": "temperature"})
    await _async_look(hass, freezer)
    still_reported = async_issue_about(issue_registry, issue_id)
    await repair.async_deactivate()

    assert reported
    assert still_reported is None
