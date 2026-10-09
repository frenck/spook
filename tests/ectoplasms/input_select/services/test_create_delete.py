"""Tests for the input_select.create and input_select.delete services.

The shared base is tested in depth with the timer. These pin what is the
input select's own: its fields, the checks it adds on top of them, and that
the base is wired to its domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.input_select import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.input_select.services import create, delete
from custom_components.spook.helper_collections import async_get_storage_collection

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er


pytestmark = pytest.mark.usefixtures("spook_translations")


@pytest.fixture(autouse=True)
async def _selects(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up one input select from the UI and one from YAML, and the actions."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "minor_version": 2,
        "data": {
            "items": [{"id": "mood", "name": "Mood", "options": ["Happy", "Sad"]}]
        },
    }
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"from_yaml": {"name": "From YAML", "options": ["One", "Two"]}}},
    )
    await hass.async_block_till_done()
    create.SpookService(hass).async_register()
    delete.SpookService(hass).async_register()


async def test_create_follows_the_name(hass: HomeAssistant) -> None:
    """Without an ID asked for, the entity ID follows the name, like the UI."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {"name": "Movie night", "options": ["Comedy", "Horror"]},
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "input_select.movie_night"}
    state = hass.states.get("input_select.movie_night")
    assert state is not None
    assert state.attributes["options"] == ["Comedy", "Horror"]
    assert state.state == "Comedy"


async def test_create_takes_the_entity_id_and_settings(hass: HomeAssistant) -> None:
    """The ID asked for wins over the name, and every setting lands."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {
            "name": "Movie night",
            "input_select_id": "movies",
            "options": ["Comedy", "Horror", "Drama"],
            "initial": "Horror",
            "icon": "mdi:movie-open",
        },
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "input_select.movies"}
    state = hass.states.get("input_select.movies")
    assert state is not None
    assert state.state == "Horror"
    assert state.attributes["options"] == ["Comedy", "Horror", "Drama"]
    assert state.attributes["icon"] == "mdi:movie-open"


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"options": ["Comedy", "Horror"], "initial": "Western"}, "not part of"),
        ({"options": ["Comedy", "Comedy"]}, "Duplicate options"),
    ],
)
async def test_create_refuses_options_that_do_not_fit(
    hass: HomeAssistant,
    settings: dict[str, Any],
    message: str,
) -> None:
    """The input select checks more than its fields, and says so readably."""
    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            DOMAIN, "create", {"name": "Broken", **settings}, blocking=True
        )
    await hass.async_block_till_done()

    assert set(async_get_storage_collection(hass, DOMAIN).data) == {"mood"}


async def test_delete_removes_the_input_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The helper goes from the state machine, the registry, and storage."""
    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "input_select.mood"}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get("input_select.mood") is None
    assert entity_registry.async_get("input_select.mood") is None
    assert "mood" not in async_get_storage_collection(hass, DOMAIN).data


async def test_delete_refuses_a_yaml_input_select_and_keeps_the_rest(
    hass: HomeAssistant,
) -> None:
    """A YAML input select late in the list keeps the ones before it."""
    with pytest.raises(HomeAssistantError, match="set up in YAML"):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: ["input_select.mood", "input_select.from_yaml"]},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get("input_select.mood") is not None
    assert hass.states.get("input_select.from_yaml") is not None
