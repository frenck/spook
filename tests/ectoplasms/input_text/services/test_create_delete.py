"""Tests for the input_text.create and input_text.delete services.

The shared base is tested in depth with the timer. These pin what is the
input text's own: its fields, the checks it adds on top of them, and that
the base is wired to its domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.input_text import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.input_text.services import create, delete
from custom_components.spook.helper_collections import async_get_storage_collection

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er


pytestmark = pytest.mark.usefixtures("spook_translations")


@pytest.fixture(autouse=True)
async def _texts(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up one input text from the UI and one from YAML, and the actions."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        # Stored the way the collection writes it: every field, defaults
        # filled in.
        "data": {
            "items": [
                {
                    "id": "note",
                    "name": "Note",
                    "min": 0,
                    "max": 100,
                    "initial": "",
                    "mode": "text",
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
        {"name": "Last message"},
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "input_text.last_message"}
    state = hass.states.get("input_text.last_message")
    assert state is not None
    assert state.attributes["mode"] == "text"


async def test_create_takes_the_entity_id_and_settings(hass: HomeAssistant) -> None:
    """The ID asked for wins over the name, and every setting lands."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {
            "name": "Last message",
            "input_text_id": "message",
            "initial": "hello",
            "min": 2,
            "max": 20,
            "pattern": "[a-z]*",
            "mode": "password",
            "icon": "mdi:message-text",
            "unit_of_measurement": "words",
        },
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "input_text.message"}
    state = hass.states.get("input_text.message")
    assert state is not None
    assert state.state == "hello"
    assert {
        key: state.attributes[key]
        for key in ("min", "max", "pattern", "mode", "icon", "unit_of_measurement")
    } == {
        "min": 2,
        "max": 20,
        "pattern": "[a-z]*",
        "mode": "password",
        "icon": "mdi:message-text",
        "unit_of_measurement": "words",
    }


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"min": 10, "max": 5}, "Max len"),
        ({"max": 3, "initial": "too long"}, "not in range"),
    ],
)
async def test_create_refuses_settings_that_do_not_fit(
    hass: HomeAssistant,
    settings: dict[str, Any],
    message: str,
) -> None:
    """The input text checks more than its fields, and says so readably."""
    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Broken", **settings},
            blocking=True,
        )

    assert hass.states.get("input_text.broken") is None


async def test_delete_removes_the_input_text(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The input text goes from the state machine, the registry, and storage."""
    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "input_text.note"}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get("input_text.note") is None
    assert entity_registry.async_get("input_text.note") is None
    assert "note" not in async_get_storage_collection(hass, DOMAIN).data


async def test_delete_refuses_a_yaml_input_text_and_keeps_the_rest(
    hass: HomeAssistant,
) -> None:
    """A YAML input text late in the list keeps the ones before it."""
    with pytest.raises(HomeAssistantError, match="set up in YAML"):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: ["input_text.note", "input_text.from_yaml"]},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get("input_text.note") is not None
    assert hass.states.get("input_text.from_yaml") is not None
