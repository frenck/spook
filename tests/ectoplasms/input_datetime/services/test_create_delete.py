"""Tests for the input_datetime.create and input_datetime.delete services.

The shared base is tested in depth with the timer. These pin what is the
input datetime's own: its fields, the checks it needs, and that the base is
wired to its domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.input_datetime import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.input_datetime.services import (
    create,
    delete,
)
from custom_components.spook.helper_collections import async_get_storage_collection

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er


pytestmark = pytest.mark.usefixtures("spook_translations")


@pytest.fixture(autouse=True)
async def _datetimes(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up one input datetime from the UI and one from YAML, and the actions."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "data": {
            "items": [
                {"id": "alarm", "name": "Alarm", "has_date": False, "has_time": True}
            ]
        },
    }
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"from_yaml": {"name": "From YAML", "has_date": True}}}
    )
    await hass.async_block_till_done()
    create.SpookService(hass).async_register()
    delete.SpookService(hass).async_register()


async def test_create_follows_the_name(hass: HomeAssistant) -> None:
    """Without an ID asked for, the entity ID follows the name, like the UI."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {"name": "Wake up", "has_time": True},
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "input_datetime.wake_up"}
    state = hass.states.get("input_datetime.wake_up")
    assert state is not None
    assert state.attributes["has_time"] is True
    assert state.attributes["has_date"] is False


async def test_create_takes_the_entity_id_and_settings(hass: HomeAssistant) -> None:
    """The ID asked for wins over the name, and every setting lands."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {
            "name": "New year",
            "input_datetime_id": "new_year",
            "has_date": True,
            "has_time": True,
            "initial": "2026-12-31 23:59:00",
            "icon": "mdi:party-popper",
        },
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "input_datetime.new_year"}
    state = hass.states.get("input_datetime.new_year")
    assert state is not None
    assert state.state == "2026-12-31 23:59:00"
    assert state.attributes["icon"] == "mdi:party-popper"


async def test_create_refuses_neither_date_nor_time(hass: HomeAssistant) -> None:
    """Both are off when left out, and a helper needs at least one."""
    with pytest.raises(HomeAssistantError, match="at least a date or a time"):
        await hass.services.async_call(
            DOMAIN, "create", {"name": "Nothing"}, blocking=True
        )

    assert hass.states.get("input_datetime.nothing") is None


async def test_create_refuses_an_unreadable_initial_value(
    hass: HomeAssistant,
) -> None:
    """An initial value it cannot read is refused before anything is stored.

    The collection does not check it, and the helper used to be stored first
    and then fail, staying behind broken while the call reported an error.
    """
    with pytest.raises(HomeAssistantError, match="can't be parsed"):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Broken", "has_date": True, "initial": "not a date"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert set(async_get_storage_collection(hass, DOMAIN).data) == {"alarm"}


async def test_delete_removes_the_input_datetime(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The helper goes from the state machine, the registry, and storage."""
    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "input_datetime.alarm"}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get("input_datetime.alarm") is None
    assert entity_registry.async_get("input_datetime.alarm") is None
    assert "alarm" not in async_get_storage_collection(hass, DOMAIN).data


async def test_delete_refuses_a_yaml_input_datetime_and_keeps_the_rest(
    hass: HomeAssistant,
) -> None:
    """A YAML input datetime late in the list keeps the ones before it."""
    with pytest.raises(HomeAssistantError, match="set up in YAML"):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: ["input_datetime.alarm", "input_datetime.from_yaml"]},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get("input_datetime.alarm") is not None
    assert hass.states.get("input_datetime.from_yaml") is not None
