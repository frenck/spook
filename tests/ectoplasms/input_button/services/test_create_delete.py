"""Tests for the input_button.create and input_button.delete services.

The shared base is tested in depth with the timer. These pin what is the
input button's own: its fields, and that the base is wired to its domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.input_button import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.input_button.services import create, delete
from custom_components.spook.helper_collections import async_get_storage_collection

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er


pytestmark = pytest.mark.usefixtures("spook_translations")


@pytest.fixture(autouse=True)
async def _buttons(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up one button from the UI and one from YAML, and the Spook actions."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "data": {"items": [{"id": "doorbell", "name": "Doorbell"}]},
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
        {"name": "Feed the cat"},
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "input_button.feed_the_cat"}
    assert hass.states.get("input_button.feed_the_cat") is not None


async def test_create_takes_the_entity_id_and_icon(hass: HomeAssistant) -> None:
    """The ID asked for wins over the name, and the icon lands."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {"name": "Feed the cat", "input_button_id": "cat", "icon": "mdi:cat"},
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "input_button.cat"}
    state = hass.states.get("input_button.cat")
    assert state is not None
    assert state.attributes["icon"] == "mdi:cat"


async def test_create_refuses_a_taken_entity_id(hass: HomeAssistant) -> None:
    """A taken ID is refused, rather than quietly getting a suffix."""
    with pytest.raises(
        HomeAssistantError, match=r"input_button\.doorbell is already taken"
    ):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Another", "input_button_id": "doorbell"},
            blocking=True,
        )


async def test_delete_removes_the_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The button goes from the state machine, the registry, and storage."""
    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "input_button.doorbell"}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get("input_button.doorbell") is None
    assert entity_registry.async_get("input_button.doorbell") is None
    assert "doorbell" not in async_get_storage_collection(hass, DOMAIN).data


async def test_delete_refuses_a_yaml_button_and_keeps_the_rest(
    hass: HomeAssistant,
) -> None:
    """A YAML button late in the list keeps the ones before it."""
    with pytest.raises(HomeAssistantError, match="set up in YAML"):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: ["input_button.doorbell", "input_button.from_yaml"]},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get("input_button.doorbell") is not None
    assert hass.states.get("input_button.from_yaml") is not None
