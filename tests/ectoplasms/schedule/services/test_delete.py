"""Tests for the schedule.delete service.

The shared base is tested in depth with the timer. These pin that the base
is wired to the schedule's domain, and tells its UI and YAML ones apart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.schedule import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.schedule.services import delete
from custom_components.spook.helper_collections import async_get_storage_collection

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from tests.common import MockUser


pytestmark = pytest.mark.usefixtures("spook_translations")

_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@pytest.fixture(autouse=True)
async def _schedules(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up two schedules from the UI and one from YAML, and the action."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "minor_version": 1,
        "data": {
            "items": [
                {"id": "heating", "name": "Heating", **{day: [] for day in _DAYS}},
                {"id": "garden", "name": "Garden", **{day: [] for day in _DAYS}},
            ]
        },
    }
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"from_yaml": {"name": "From YAML"}}},
    )
    await hass.async_block_till_done()
    delete.SpookService(hass).async_register()


async def test_delete_removes_the_schedules(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The schedules go from the state machine, the registry, and storage."""
    await hass.services.async_call(
        DOMAIN,
        "delete",
        {ATTR_ENTITY_ID: ["schedule.heating", "schedule.garden"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    for entity_id in ("schedule.heating", "schedule.garden"):
        assert hass.states.get(entity_id) is None
        assert entity_registry.async_get(entity_id) is None
    assert not async_get_storage_collection(hass, DOMAIN).data
    assert hass.states.get("schedule.from_yaml") is not None


async def test_delete_a_disabled_schedule(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """A disabled schedule is not running, but it is still there to delete."""
    entity_registry.async_update_entity(
        "schedule.heating", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert hass.states.get("schedule.heating") is None

    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "schedule.heating"}, blocking=True
    )
    await hass.async_block_till_done()

    assert "heating" not in async_get_storage_collection(hass, DOMAIN).data
    assert entity_registry.async_get("schedule.heating") is None


async def test_delete_the_same_schedule_twice_in_a_list(
    hass: HomeAssistant,
) -> None:
    """A duplicate in the list is not an error after the schedule is gone."""
    await hass.services.async_call(
        DOMAIN,
        "delete",
        {ATTR_ENTITY_ID: ["schedule.heating", "schedule.heating"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("schedule.heating") is None


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ("schedule.nope", "Entity schedule.nope not found"),
        ("schedule.from_yaml", r"schedule\.from_yaml is set up in YAML"),
    ],
)
async def test_a_bad_schedule_in_a_list_deletes_none_of_them(
    hass: HomeAssistant,
    bad: str,
    message: str,
) -> None:
    """A schedule that cannot go, late in the list, keeps the ones before it."""
    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: ["schedule.heating", bad]},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get("schedule.heating") is not None
    assert hass.states.get("schedule.from_yaml") is not None


async def test_only_an_admin_can_delete(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
) -> None:
    """Removing a helper is configuration, not everyday use."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: "schedule.heating"},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    assert hass.states.get("schedule.heating") is not None
