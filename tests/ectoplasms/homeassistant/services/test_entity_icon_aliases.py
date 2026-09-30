"""Tests for the entity icon and alias actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.ectoplasms.homeassistant.services import (
    add_alias_to_entity,
    remove_alias_from_entity,
    set_entity_aliases,
    set_entity_icon,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from tests.common import MockUser

OWN_NAME = er.COMPUTED_NAME


@pytest.fixture(autouse=True)
async def _register(hass: HomeAssistant) -> None:
    """Register the four actions."""
    assert await async_setup_component(hass, "homeassistant", {})
    for module in (
        set_entity_icon,
        add_alias_to_entity,
        remove_alias_from_entity,
        set_entity_aliases,
    ):
        module.SpookService(hass).async_register()
    await hass.async_block_till_done()


def _entity(
    entity_registry: er.EntityRegistry, object_id: str, aliases: list[Any] | None = None
) -> str:
    """Register a light, with the aliases a new entity gets unless told otherwise."""
    entity_id = entity_registry.async_get_or_create(
        "light", "test", object_id, suggested_object_id=object_id
    ).entity_id
    if aliases is not None:
        entity_registry.async_update_entity(entity_id, aliases=aliases)
    return entity_id


async def _call(hass: HomeAssistant, service: str, **data: Any) -> None:
    """Call one of the actions."""
    await hass.services.async_call("homeassistant", service, data, blocking=True)


def _aliases(entity_registry: er.EntityRegistry, entity_id: str) -> list[Any]:
    """Return an entity's aliases, in order."""
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    return list(entry.aliases)


async def test_set_icon_and_take_it_away_again(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Null takes the icon away, back to the integration's own."""
    lamps = [_entity(entity_registry, "one"), _entity(entity_registry, "two")]

    await _call(hass, "set_entity_icon", entity_id=lamps, icon="mdi:lamp")
    assert {entity_registry.async_get(lamp).icon for lamp in lamps} == {"mdi:lamp"}

    await _call(hass, "set_entity_icon", entity_id=lamps, icon=None)
    assert {entity_registry.async_get(lamp).icon for lamp in lamps} == {None}


async def test_a_new_entity_starts_with_its_own_name(
    entity_registry: er.EntityRegistry,
) -> None:
    """The premise the alias actions are built around, checked against core."""
    assert _aliases(entity_registry, _entity(entity_registry, "new")) == [OWN_NAME]


async def test_add_appends_skips_repeats_and_keeps_the_own_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """New ones at the end, trimmed, and nothing twice."""
    lamp = _entity(entity_registry, "lamp", [OWN_NAME, "Reading lamp"])

    await _call(
        hass,
        "add_alias_to_entity",
        entity_id=lamp,
        alias=["  Big light ", "Reading lamp", "", "Big light"],
    )

    assert _aliases(entity_registry, lamp) == [OWN_NAME, "Reading lamp", "Big light"]


async def test_remove_takes_only_the_named_ones(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The own name is not something to remove by naming it."""
    lamp = _entity(entity_registry, "lamp", ["Reading lamp", OWN_NAME, "Big light"])

    await _call(
        hass, "remove_alias_from_entity", entity_id=lamp, alias=[" Big light", "Nope"]
    )

    assert _aliases(entity_registry, lamp) == ["Reading lamp", OWN_NAME]


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ([OWN_NAME, "Old"], [OWN_NAME, "Reading lamp", "Big light"]),
        (["Old", OWN_NAME], [OWN_NAME, "Reading lamp", "Big light"]),
        (["Old"], ["Reading lamp", "Big light"]),
    ],
)
async def test_set_replaces_and_keeps_the_own_name_as_it_was(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    before: list[Any],
    after: list[Any],
) -> None:
    """Replaced, with the own name kept up front only where it was there."""
    lamp = _entity(entity_registry, "lamp", before)

    await _call(
        hass,
        "set_entity_aliases",
        entity_id=lamp,
        aliases=["Reading lamp", " Big light ", "", "Reading lamp"],
    )

    assert _aliases(entity_registry, lamp) == after


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("set_entity_icon", {"icon": "mdi:lamp"}),
        ("add_alias_to_entity", {"alias": "Lamp"}),
        ("remove_alias_from_entity", {"alias": "Old"}),
        ("set_entity_aliases", {"aliases": "Lamp"}),
    ],
)
async def test_a_bad_entity_in_a_list_changes_none_of_them(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    service: str,
    data: dict[str, Any],
) -> None:
    """A typo late in the list leaves the first ones as they were."""
    lamp = _entity(entity_registry, "lamp", [OWN_NAME, "Old"])

    with pytest.raises(HomeAssistantError, match=r"light\.nope not found"):
        await _call(hass, service, entity_id=[lamp, "light.nope"], **data)

    entry = entity_registry.async_get(lamp)
    assert entry is not None
    assert (entry.icon, list(entry.aliases)) == (None, [OWN_NAME, "Old"])


async def test_an_entity_without_a_unique_id_says_why(hass: HomeAssistant) -> None:
    """It exists, but Home Assistant has nowhere to keep an icon for it."""
    hass.states.async_set("light.yaml_only", "on")

    with pytest.raises(HomeAssistantError, match="has no unique ID"):
        await _call(hass, "set_entity_icon", entity_id="light.yaml_only", icon=None)


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("set_entity_icon", {"icon": "mdi:lamp"}),
        ("add_alias_to_entity", {"alias": "Lamp"}),
        ("remove_alias_from_entity", {"alias": "Old"}),
        ("set_entity_aliases", {"aliases": "Lamp"}),
    ],
)
async def test_only_an_admin_can_change_them(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_read_only_user: MockUser,
    service: str,
    data: dict[str, Any],
) -> None:
    """Like the other registry actions: this is configuration."""
    lamp = _entity(entity_registry, "lamp", [OWN_NAME, "Old"])

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "homeassistant",
            service,
            {"entity_id": lamp, **data},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
