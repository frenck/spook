"""Tests for the input_boolean.create and input_boolean.delete services.

The shared base is tested in depth with the timer. These pin what is the
input boolean's own: its fields, and that the base is wired to its domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.input_boolean import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.input_boolean.services import create, delete
from custom_components.spook.helper_collections import async_get_storage_collection

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
async def _toggles(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up one toggle from the UI and one from YAML, and the Spook actions."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "data": {"items": [{"id": "away", "name": "Away"}]},
    }
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"from_yaml": {"name": "From YAML"}}}
    )
    await hass.async_block_till_done()
    create.SpookService(hass).async_register()
    delete.SpookService(hass).async_register()


async def test_create_follows_the_name(hass: HomeAssistant) -> None:
    """Without an ID asked for, the entity ID follows the name, like the UI."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {"name": "Guest mode"},
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "input_boolean.guest_mode"}
    state = hass.states.get("input_boolean.guest_mode")
    assert state is not None
    assert state.state == STATE_OFF


async def test_create_takes_the_entity_id_and_settings(hass: HomeAssistant) -> None:
    """The ID asked for wins over the name, and every setting lands."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {
            "name": "Guest mode",
            "input_boolean_id": "guests",
            "initial": True,
            "icon": "mdi:account-multiple",
        },
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "input_boolean.guests"}
    state = hass.states.get("input_boolean.guests")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["icon"] == "mdi:account-multiple"


async def test_create_refuses_a_taken_entity_id(hass: HomeAssistant) -> None:
    """A taken ID is refused, rather than quietly getting a suffix."""
    with pytest.raises(
        HomeAssistantError, match=r"input_boolean\.away is already taken"
    ):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Another", "input_boolean_id": "away"},
            blocking=True,
        )


async def test_delete_removes_the_toggle(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The toggle goes from the state machine, the registry, and storage."""
    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "input_boolean.away"}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get("input_boolean.away") is None
    assert entity_registry.async_get("input_boolean.away") is None
    assert "away" not in async_get_storage_collection(hass, DOMAIN).data


async def test_delete_a_disabled_toggle(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """A disabled toggle is not running, but it is still there to delete."""
    entity_registry.async_update_entity(
        "input_boolean.away", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "input_boolean.away"}, blocking=True
    )
    await hass.async_block_till_done()

    assert "away" not in async_get_storage_collection(hass, DOMAIN).data


async def test_delete_refuses_a_yaml_toggle_and_keeps_the_rest(
    hass: HomeAssistant,
) -> None:
    """A YAML toggle late in the list keeps the ones before it."""
    with pytest.raises(HomeAssistantError, match="set up in YAML"):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: ["input_boolean.away", "input_boolean.from_yaml"]},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get("input_boolean.away") is not None
    assert hass.states.get("input_boolean.from_yaml") is not None
