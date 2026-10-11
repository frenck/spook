"""Tests for the homeassistant.update_floor action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.setup import async_setup_component
import voluptuous as vol

import pytest

from custom_components.spook.ectoplasms.homeassistant.services import update_floor

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import area_registry as ar, floor_registry as fr

    from tests.common import MockUser


pytestmark = pytest.mark.usefixtures("spook_translations")


async def _setup(hass: HomeAssistant) -> None:
    """Register the action."""
    assert await async_setup_component(hass, "homeassistant", {})
    update_floor.SpookService(hass).async_register()
    await hass.async_block_till_done()


async def _update(
    hass: HomeAssistant, context: Context | None = None, **data: object
) -> None:
    """Call the action."""
    await hass.services.async_call(
        "homeassistant", "update_floor", dict(data), blocking=True, context=context
    )


async def test_every_field_can_be_changed(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Each field the UI can change, changed through the action itself."""
    floor = floor_registry.async_create("First floor", level=1)
    await _setup(hass)

    await _update(
        hass,
        floor_id=floor.floor_id,
        name="Ground floor",
        aliases=["Downstairs", "Begane grond"],
        icon="mdi:home-floor-g",
        level=0,
    )

    updated = floor_registry.async_get_floor(floor.floor_id)
    assert updated.name == "Ground floor"
    assert updated.aliases == {"Downstairs", "Begane grond"}
    assert updated.icon == "mdi:home-floor-g"
    assert updated.level == 0


async def test_it_leaves_alone_what_the_call_did_not_mention(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """The reason this action exists at all.

    Somebody changing an icon wants the name, level and aliases they already
    picked to survive it, and every area on the floor to stay there. Deleting
    and creating the floor again took all of that.
    """
    floor = floor_registry.async_create(
        "First floor", aliases={"Downstairs"}, icon="mdi:floor-1", level=1
    )
    area = area_registry.async_create("Living room", floor_id=floor.floor_id)
    await _setup(hass)

    await _update(hass, floor_id=floor.floor_id, icon="mdi:home-floor-1")

    updated = floor_registry.async_get_floor(floor.floor_id)
    assert updated.icon == "mdi:home-floor-1"
    assert updated.name == "First floor"
    assert updated.aliases == {"Downstairs"}
    assert updated.level == 1
    assert area_registry.async_get_area(area.id).floor_id == floor.floor_id


async def test_null_clears_a_field_where_leaving_it_out_would_keep_it(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """A floor without a level is one the UI can make, so this can too."""
    floor = floor_registry.async_create("Attic", icon="mdi:home-roof", level=2)
    await _setup(hass)

    await _update(hass, floor_id=floor.floor_id, icon=None, level=None)

    updated = floor_registry.async_get_floor(floor.floor_id)
    assert updated.icon is None
    assert updated.level is None
    assert updated.name == "Attic"


async def test_a_quoted_level_is_taken_as_a_number(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """A level in quotes is still a level, as it is for create_floor."""
    floor = floor_registry.async_create("Basement")
    await _setup(hass)

    await _update(hass, floor_id=floor.floor_id, level="-1")

    assert floor_registry.async_get_floor(floor.floor_id).level == -1


async def test_aliases_are_replaced_and_an_empty_list_clears_them(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Replaced, like set_floor_aliases does and the UI does."""
    floor = floor_registry.async_create("First floor", aliases={"Downstairs"})
    await _setup(hass)

    await _update(hass, floor_id=floor.floor_id, aliases="Ground floor")
    assert floor_registry.async_get_floor(floor.floor_id).aliases == {"Ground floor"}

    await _update(hass, floor_id=floor.floor_id, aliases=[])
    assert floor_registry.async_get_floor(floor.floor_id).aliases == set()


async def test_a_floor_that_does_not_exist_is_refused(
    hass: HomeAssistant,
) -> None:
    """Core raises a bare KeyError on this, which surfaces as an unknown error."""
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match=r"Floor no_such_floor not found"):
        await _update(hass, floor_id="no_such_floor", name="Ghosts")


async def test_a_call_that_changes_nothing_is_refused(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """A misspelled field name would otherwise be a successful no-op."""
    floor = floor_registry.async_create("First floor")
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match="Nothing to update"):
        await _update(hass, floor_id=floor.floor_id)


async def test_renaming_onto_another_floor_says_so(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Core raises a bare ValueError here, which surfaces as an unknown error.

    Names match ignoring case and spaces, so a different spelling of a taken
    name is just as taken.
    """
    attic = floor_registry.async_create("Attic")
    floor = floor_registry.async_create("First floor", icon="mdi:floor-1")
    await _setup(hass)

    with pytest.raises(
        HomeAssistantError,
        match=f"The name AT TIC is already taken by floor {attic.floor_id}",
    ):
        await _update(hass, floor_id=floor.floor_id, name="AT TIC", icon=None)

    unchanged = floor_registry.async_get_floor(floor.floor_id)
    assert unchanged.name == "First floor"
    assert unchanged.icon == "mdi:floor-1"


async def test_a_floor_can_be_renamed_to_another_spelling_of_its_own_name(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """The name it collides with is its own, which is not a collision."""
    floor = floor_registry.async_create("First floor")
    await _setup(hass)

    await _update(hass, floor_id=floor.floor_id, name="First Floor")

    assert floor_registry.async_get_floor(floor.floor_id).name == "First Floor"


async def test_a_floor_cannot_be_left_without_a_name(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Nullable fields are cleared by `None`, the name is not one of them."""
    floor = floor_registry.async_create("First floor")
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await _update(hass, floor_id=floor.floor_id, name=None)

    assert floor_registry.async_get_floor(floor.floor_id).name == "First floor"


async def test_only_an_admin_can_update_a_floor(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
    hass_read_only_user: MockUser,
) -> None:
    """Floors are the same for every user, so changing one takes an admin."""
    floor = floor_registry.async_create("First floor")
    await _setup(hass)

    with pytest.raises(Unauthorized):
        await _update(
            hass,
            context=Context(user_id=hass_read_only_user.id),
            floor_id=floor.floor_id,
            name="Ground floor",
        )

    assert floor_registry.async_get_floor(floor.floor_id).name == "First floor"
