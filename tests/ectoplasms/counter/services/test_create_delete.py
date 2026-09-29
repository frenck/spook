"""Tests for the counter.create and counter.delete services.

The shared base is tested in depth with the timer. These pin what is the
counter's own: its fields, and that the base is wired to its domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.counter import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.counter.services import create, delete
from custom_components.spook.helper_collections import async_get_storage_collection

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
async def _counters(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up one counter from the UI and one from YAML, and the Spook actions."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        # Stored the way the collection writes it: every field, defaults
        # filled in. Counter setup does not fill them in on load.
        "data": {
            "items": [
                {
                    "id": "visits",
                    "name": "Visits",
                    "initial": 0,
                    "minimum": None,
                    "maximum": None,
                    "step": 1,
                    "restore": True,
                }
            ]
        },
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
        {"name": "Coffee cups"},
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "counter.coffee_cups"}
    state = hass.states.get("counter.coffee_cups")
    assert state is not None
    assert state.state == "0"
    assert state.attributes["step"] == 1


async def test_create_takes_the_entity_id_and_settings(hass: HomeAssistant) -> None:
    """The ID asked for wins over the name, and every setting lands."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {
            "name": "Coffee cups",
            "counter_id": "coffee",
            "initial": 2,
            "minimum": 0,
            "maximum": 10,
            "step": 2,
            "restore": False,
            "icon": "mdi:coffee",
        },
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "counter.coffee"}
    state = hass.states.get("counter.coffee")
    assert state is not None
    assert state.state == "2"
    assert {
        key: state.attributes[key] for key in ("minimum", "maximum", "step", "icon")
    } == {"minimum": 0, "maximum": 10, "step": 2, "icon": "mdi:coffee"}


async def test_create_refuses_a_taken_entity_id(hass: HomeAssistant) -> None:
    """A taken ID is refused, rather than quietly getting a suffix."""
    with pytest.raises(HomeAssistantError, match=r"counter\.visits is already taken"):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Another", "counter_id": "visits"},
            blocking=True,
        )


async def test_delete_removes_the_counter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The counter goes from the state machine, the registry, and storage."""
    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "counter.visits"}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get("counter.visits") is None
    assert entity_registry.async_get("counter.visits") is None
    assert "visits" not in async_get_storage_collection(hass, DOMAIN).data


async def test_delete_a_disabled_counter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """A disabled counter is not running, but it is still there to delete."""
    entity_registry.async_update_entity(
        "counter.visits", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "counter.visits"}, blocking=True
    )
    await hass.async_block_till_done()

    assert "visits" not in async_get_storage_collection(hass, DOMAIN).data


async def test_delete_refuses_a_yaml_counter_and_keeps_the_rest(
    hass: HomeAssistant,
) -> None:
    """A YAML counter late in the list keeps the ones before it."""
    with pytest.raises(HomeAssistantError, match="set up in YAML"):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: ["counter.visits", "counter.from_yaml"]},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get("counter.visits") is not None
    assert hass.states.get("counter.from_yaml") is not None
