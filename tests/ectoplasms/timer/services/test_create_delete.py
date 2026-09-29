"""Tests for the timer.create and timer.delete services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.timer import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.timer.services import create, delete
from custom_components.spook.helper_collections import async_get_storage_collection

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from tests.common import MockUser


@pytest.fixture(autouse=True)
async def _timers(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up one timer from the UI and one from YAML, and the Spook actions."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "data": {
            "items": [
                {"id": "mist", "name": "Mist", "duration": "0:05:00"},
            ]
        },
    }
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"from_yaml": {"duration": 60}}}
    )
    await hass.async_block_till_done()
    create.SpookService(hass).async_register()
    delete.SpookService(hass).async_register()


async def test_create_follows_the_name(hass: HomeAssistant) -> None:
    """Without an ID asked for, the entity ID follows the name, like the UI."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {"name": "Greenhouse fan"},
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "timer.greenhouse_fan"}
    state = hass.states.get("timer.greenhouse_fan")
    assert state is not None
    assert state.attributes["duration"] == "0:00:00"


async def test_create_takes_the_entity_id_and_settings(hass: HomeAssistant) -> None:
    """The ID asked for wins over the name, and every setting lands."""
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {
            "name": "Greenhouse fan",
            "timer_id": "fan",
            "duration": {"minutes": 10},
            "restore": True,
            "icon": "mdi:fan",
        },
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "timer.fan"}
    state = hass.states.get("timer.fan")
    assert state is not None
    assert state.attributes["duration"] == "0:10:00"
    assert state.attributes["restore"] is True
    assert state.attributes["icon"] == "mdi:fan"


async def test_create_works_without_asking_for_the_response(
    hass: HomeAssistant,
) -> None:
    """Most scripts will just want the timer, not to be told its name."""
    await hass.services.async_call(DOMAIN, "create", {"name": "Water"}, blocking=True)

    assert hass.states.get("timer.water") is not None


@pytest.mark.parametrize("taken", ["mist", "from_yaml"])
async def test_create_refuses_an_entity_id_already_taken(
    hass: HomeAssistant,
    taken: str,
) -> None:
    """A taken ID is refused, rather than quietly getting a suffix."""
    with pytest.raises(HomeAssistantError, match=f"timer.{taken} is already taken"):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Another", "timer_id": taken},
            blocking=True,
        )


async def test_create_refuses_an_entity_id_held_only_by_the_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """A disabled entity has no state, but its entity ID is still taken."""
    entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "disabled",
        suggested_object_id="reserved",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert hass.states.get("timer.reserved") is None

    with pytest.raises(HomeAssistantError, match=r"timer\.reserved is already taken"):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Another", "timer_id": "reserved"},
            blocking=True,
        )


async def test_create_refuses_an_entity_id_reserved_for_another(
    hass: HomeAssistant,
) -> None:
    """An entity being added holds its ID before it has a state."""
    hass.states.async_reserve("timer.on_its_way")

    with pytest.raises(HomeAssistantError, match=r"timer\.on_its_way is already taken"):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Another", "timer_id": "on_its_way"},
            blocking=True,
        )


async def test_a_failed_rename_leaves_no_timer_behind(hass: HomeAssistant) -> None:
    """Taken between the check and the rename: the new timer goes again."""
    with (
        patch.object(
            er.EntityRegistry,
            "async_update_entity",
            side_effect=ValueError("Entity is already registered"),
        ),
        pytest.raises(HomeAssistantError, match=r"timer\.lost is already taken"),
    ):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Stray", "timer_id": "lost"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert set(async_get_storage_collection(hass, DOMAIN).data) == {"mist"}
    assert hass.states.get("timer.stray") is None


async def test_delete_a_disabled_timer(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """A disabled timer is not running, but it is still there to delete."""
    entity_registry.async_update_entity(
        "timer.mist", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert hass.states.get("timer.mist") is None

    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "timer.mist"}, blocking=True
    )
    await hass.async_block_till_done()

    assert "mist" not in async_get_storage_collection(hass, DOMAIN).data
    assert entity_registry.async_get("timer.mist") is None


async def test_create_refusal_from_the_collection_reads_well(
    hass: HomeAssistant,
) -> None:
    """A refusal from inside the collection comes back as a readable error."""
    collection = async_get_storage_collection(hass, DOMAIN)

    with (
        patch.object(
            collection,
            "async_create_item",
            side_effect=vol.Invalid("That will not do"),
        ),
        pytest.raises(HomeAssistantError, match="That will not do"),
    ):
        await hass.services.async_call(
            DOMAIN, "create", {"name": "Refused"}, blocking=True
        )


async def test_delete_removes_the_timer(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The timer goes from the state machine, the registry, and storage."""
    await hass.services.async_call(
        DOMAIN, "delete", {ATTR_ENTITY_ID: "timer.mist"}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get("timer.mist") is None
    assert entity_registry.async_get("timer.mist") is None
    assert "mist" not in async_get_storage_collection(hass, DOMAIN).data


async def test_delete_the_same_timer_twice_in_a_list(hass: HomeAssistant) -> None:
    """A duplicate in the list is not an error after the timer is gone."""
    await hass.services.async_call(
        DOMAIN,
        "delete",
        {ATTR_ENTITY_ID: ["timer.mist", "timer.mist"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("timer.mist") is None


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ("timer.nope", "Could not find timer.nope"),
        ("timer.from_yaml", "set up in YAML"),
    ],
)
async def test_a_bad_timer_in_a_list_deletes_none_of_them(
    hass: HomeAssistant,
    bad: str,
    message: str,
) -> None:
    """A timer that cannot go, late in the list, keeps the ones before it."""
    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: ["timer.mist", bad]},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get("timer.mist") is not None


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("create", {"name": "Sneaky"}),
        ("delete", {ATTR_ENTITY_ID: "timer.mist"}),
    ],
)
async def test_only_an_admin_can_create_or_delete(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    service: str,
    data: dict[str, Any],
) -> None:
    """Making and removing helpers is configuration, not everyday use."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            service,
            data,
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    assert hass.states.get("timer.mist") is not None
    assert hass.states.get("timer.sneaky") is None


async def test_an_unreachable_collection_says_so(hass: HomeAssistant) -> None:
    """If core moves the collection, the error says what broke."""
    del hass.data["websocket_api"]["timer/list"]

    with pytest.raises(HomeAssistantError, match="Could not reach the timer helpers"):
        await hass.services.async_call(
            DOMAIN, "create", {"name": "Lost"}, blocking=True
        )
