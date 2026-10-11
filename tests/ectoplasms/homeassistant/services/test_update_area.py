"""Tests for the homeassistant.update_area action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.setup import async_setup_component
import voluptuous as vol

import pytest

from custom_components.spook.ectoplasms.homeassistant.services import update_area

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        area_registry as ar,
        floor_registry as fr,
        label_registry as lr,
    )

    from tests.common import MockUser


pytestmark = pytest.mark.usefixtures("spook_translations")


async def _setup(hass: HomeAssistant) -> None:
    """Register the action."""
    assert await async_setup_component(hass, "homeassistant", {})
    update_area.SpookService(hass).async_register()
    await hass.async_block_till_done()


async def _update(
    hass: HomeAssistant, context: Context | None = None, **data: object
) -> None:
    """Call the action."""
    await hass.services.async_call(
        "homeassistant", "update_area", dict(data), blocking=True, context=context
    )


def _sensors(hass: HomeAssistant) -> None:
    """Set up a temperature and a humidity sensor, the kinds an area takes."""
    hass.states.async_set("sensor.temperature", "21", {"device_class": "temperature"})
    hass.states.async_set("sensor.humidity", "55", {"device_class": "humidity"})


async def test_every_field_can_be_changed(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Each field the UI can change, changed through the action itself."""
    floor = floor_registry.async_create("Ground floor")
    label = label_registry.async_create("Cozy")
    area = area_registry.async_create("Lounge")
    _sensors(hass)
    await _setup(hass)

    await _update(
        hass,
        area_id=area.id,
        name="Living room",
        aliases=["Sitting area", "Den"],
        floor_id=floor.floor_id,
        icon="mdi:sofa",
        picture="/local/living_room.jpg",
        labels=[label.label_id],
        temperature_entity_id="sensor.temperature",
        humidity_entity_id="sensor.humidity",
    )

    updated = area_registry.async_get_area(area.id)
    assert updated.name == "Living room"
    assert updated.aliases == {"Sitting area", "Den"}
    assert updated.floor_id == floor.floor_id
    assert updated.icon == "mdi:sofa"
    assert updated.picture == "/local/living_room.jpg"
    assert updated.labels == {label.label_id}
    assert updated.temperature_entity_id == "sensor.temperature"
    assert updated.humidity_entity_id == "sensor.humidity"


async def test_it_leaves_alone_what_the_call_did_not_mention(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """The reason this action exists at all.

    Somebody changing an icon wants the floor, labels and aliases they already
    picked to survive it. Passing every field through would read an
    unmentioned floor as "take it off its floor".
    """
    floor = floor_registry.async_create("Ground floor")
    label = label_registry.async_create("Cozy")
    area = area_registry.async_create(
        "Living room",
        aliases={"Lounge"},
        floor_id=floor.floor_id,
        icon="mdi:sofa",
        labels={label.label_id},
        picture="/local/living_room.jpg",
    )
    await _setup(hass)

    await _update(hass, area_id=area.id, icon="mdi:television")

    updated = area_registry.async_get_area(area.id)
    assert updated.icon == "mdi:television"
    assert updated.name == "Living room"
    assert updated.aliases == {"Lounge"}
    assert updated.floor_id == floor.floor_id
    assert updated.labels == {label.label_id}
    assert updated.picture == "/local/living_room.jpg"


async def test_null_clears_a_field_where_leaving_it_out_would_keep_it(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Without this there is no way to take an area back off its floor."""
    floor = floor_registry.async_create("Ground floor")
    _sensors(hass)
    area = area_registry.async_create(
        "Living room",
        floor_id=floor.floor_id,
        humidity_entity_id="sensor.humidity",
        icon="mdi:sofa",
        picture="/local/living_room.jpg",
        temperature_entity_id="sensor.temperature",
    )
    await _setup(hass)

    await _update(
        hass,
        area_id=area.id,
        floor_id=None,
        icon=None,
        picture=None,
        temperature_entity_id=None,
        humidity_entity_id=None,
    )

    updated = area_registry.async_get_area(area.id)
    assert updated.floor_id is None
    assert updated.icon is None
    assert updated.picture is None
    assert updated.temperature_entity_id is None
    assert updated.humidity_entity_id is None
    assert updated.name == "Living room"


async def test_aliases_and_labels_are_replaced_and_an_empty_list_clears_them(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Replaced, like set_area_aliases does and the UI does.

    Adding or removing one is what the add and remove actions are for.
    """
    cozy = label_registry.async_create("Cozy")
    warm = label_registry.async_create("Warm")
    area = area_registry.async_create(
        "Living room", aliases={"Lounge"}, labels={cozy.label_id}
    )
    await _setup(hass)

    await _update(hass, area_id=area.id, aliases="Den", labels=warm.label_id)

    updated = area_registry.async_get_area(area.id)
    assert updated.aliases == {"Den"}
    assert updated.labels == {warm.label_id}

    await _update(hass, area_id=area.id, aliases=[], labels=[])

    updated = area_registry.async_get_area(area.id)
    assert updated.aliases == set()
    assert updated.labels == set()


async def test_an_area_that_does_not_exist_is_refused(
    hass: HomeAssistant,
) -> None:
    """Core raises a bare KeyError on this, which surfaces as an unknown error."""
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match=r"Area no_such_area not found"):
        await _update(hass, area_id="no_such_area", name="Ghosts")


async def test_a_call_that_changes_nothing_is_refused(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """A misspelled field name would otherwise be a successful no-op."""
    area = area_registry.async_create("Living room")
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match="Nothing to update"):
        await _update(hass, area_id=area.id)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"floor_id": "attic"}, "Floor attic not found"),
        ({"labels": ["cozy", "no_such_label"]}, "Label no_such_label not found"),
        (
            {"temperature_entity_id": "sensor.nowhere"},
            "Entity sensor.nowhere not found",
        ),
        (
            {"humidity_entity_id": "sensor.nowhere"},
            "Entity sensor.nowhere not found",
        ),
    ],
)
async def test_an_unknown_reference_is_refused(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    label_registry: lr.LabelRegistry,
    data: dict[str, object],
    message: str,
) -> None:
    """The registry stores a floor or label that does not exist without a word.

    The area then sits on a floor nobody can find, and nothing says why.
    Nothing is changed either, not even the part of the call that was fine.
    """
    label_registry.async_create("Cozy")
    area = area_registry.async_create("Living room")
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match=message):
        await _update(hass, area_id=area.id, name="Lounge", **data)

    unchanged = area_registry.async_get_area(area.id)
    assert unchanged.name == "Living room"
    assert unchanged.floor_id is None
    assert unchanged.labels == set()
    assert unchanged.temperature_entity_id is None
    assert unchanged.humidity_entity_id is None


async def test_a_sensor_of_the_wrong_kind_is_refused(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """The registry checks this one itself, and its reason is passed on."""
    _sensors(hass)
    area = area_registry.async_create("Living room")
    await _setup(hass)

    with pytest.raises(
        HomeAssistantError,
        match=(
            r"Area living_room cannot be changed like that: "
            r"Entity sensor.humidity is not a temperature sensor"
        ),
    ):
        await _update(hass, area_id=area.id, temperature_entity_id="sensor.humidity")

    assert area_registry.async_get_area(area.id).temperature_entity_id is None


async def test_renaming_onto_another_area_says_so(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """Core raises a bare ValueError here, which surfaces as an unknown error.

    Names match ignoring case and spaces, so a different spelling of a taken
    name is just as taken.
    """
    kitchen = area_registry.async_create("Kitchen")
    area = area_registry.async_create("Living room")
    await _setup(hass)

    with pytest.raises(
        HomeAssistantError,
        match=f"The name KIT CHEN is already taken by area {kitchen.id}",
    ):
        await _update(hass, area_id=area.id, name="KIT CHEN")

    assert area_registry.async_get_area(area.id).name == "Living room"


async def test_an_area_can_be_renamed_to_another_spelling_of_its_own_name(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """The name it collides with is its own, which is not a collision."""
    area = area_registry.async_create("Living room")
    await _setup(hass)

    await _update(hass, area_id=area.id, name="Living Room")

    assert area_registry.async_get_area(area.id).name == "Living Room"


async def test_an_area_cannot_be_left_without_a_name(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """Nullable fields are cleared by `None`, the name is not one of them."""
    area = area_registry.async_create("Living room")
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await _update(hass, area_id=area.id, name=None)

    assert area_registry.async_get_area(area.id).name == "Living room"


async def test_only_an_admin_can_update_an_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    hass_read_only_user: MockUser,
) -> None:
    """Areas are the same for every user, so changing one takes an admin."""
    area = area_registry.async_create("Living room")
    await _setup(hass)

    with pytest.raises(Unauthorized):
        await _update(
            hass,
            context=Context(user_id=hass_read_only_user.id),
            area_id=area.id,
            name="Lounge",
        )

    assert area_registry.async_get_area(area.id).name == "Living room"
