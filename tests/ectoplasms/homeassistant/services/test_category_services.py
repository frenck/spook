"""Tests for the category actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.homeassistant.services import (
    add_category_to_entity,
    create_category,
    delete_category,
    remove_category_from_entity,
    update_category,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        category_registry as cr,
        entity_registry as er,
    )

pytestmark = pytest.mark.usefixtures("spook_translations")


_MODULES = (
    create_category,
    update_category,
    delete_category,
    add_category_to_entity,
    remove_category_from_entity,
)


@pytest.fixture(autouse=True)
async def _register(hass: HomeAssistant) -> None:
    """Register every category action."""
    assert await async_setup_component(hass, "homeassistant", {})
    for module in _MODULES:
        module.SpookService(hass).async_register()
    await hass.async_block_till_done()


async def _call(hass: HomeAssistant, service: str, **data: object) -> object:
    """Call one of the category actions."""
    return await hass.services.async_call("homeassistant", service, data, blocking=True)


def _entity(entity_registry: er.EntityRegistry, domain: str, name: str) -> str:
    """Register an entity and return its ID."""
    return entity_registry.async_get_or_create(
        domain, "test", name, suggested_object_id=name
    ).entity_id


async def test_create_hands_back_the_new_id(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
) -> None:
    """A category ID is random, so without it an automation could not use it."""
    response = await hass.services.async_call(
        "homeassistant",
        "create_category",
        {"scope": "automation", "name": "Lights", "icon": "mdi:lightbulb"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    category = category_registry.async_get_category(
        scope="automation", category_id=response["category_id"]
    )
    assert category is not None
    assert category.name == "Lights"
    assert category.icon == "mdi:lightbulb"


async def test_create_works_without_asking_for_the_response(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
) -> None:
    """Most automations will just want the category, not its ID."""
    await _call(hass, "create_category", scope="script", name="Morning")

    assert [
        category.name
        for category in category_registry.async_list_categories(scope="script")
    ] == ["Morning"]


async def test_create_refuses_a_name_already_taken(hass: HomeAssistant) -> None:
    """Two categories with one name on one page cannot be told apart."""
    await _call(hass, "create_category", scope="automation", name="Lights")

    with pytest.raises(HomeAssistantError, match="already"):
        await _call(hass, "create_category", scope="automation", name="Lights")


async def test_create_refuses_a_scope_no_page_shows(hass: HomeAssistant) -> None:
    """Home Assistant takes any scope, and a typo would make a category nobody sees."""
    with pytest.raises(vol.Invalid):
        await _call(hass, "create_category", scope="automations", name="Lights")


async def test_update_by_name_keeps_what_is_left_out(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
) -> None:
    """Renaming does not take the icon with it."""
    category = category_registry.async_create(
        scope="automation", name="Lights", icon="mdi:lightbulb"
    )

    await _call(
        hass,
        "update_category",
        scope="automation",
        category_id="lights",
        name="Lighting",
    )

    updated = category_registry.async_get_category(
        scope="automation", category_id=category.category_id
    )
    assert updated is not None
    assert updated.name == "Lighting"
    assert updated.icon == "mdi:lightbulb"


async def test_update_clears_the_icon_with_null(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
) -> None:
    """Null means clear, which is different from leaving it out."""
    category = category_registry.async_create(
        scope="helpers", name="Climate", icon="mdi:thermometer"
    )

    await _call(
        hass,
        "update_category",
        scope="helpers",
        category_id=category.category_id,
        icon=None,
    )

    updated = category_registry.async_get_category(
        scope="helpers", category_id=category.category_id
    )
    assert updated is not None
    assert updated.icon is None


async def test_update_refuses_to_change_nothing(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
) -> None:
    """A misspelled field would otherwise pass for a successful update."""
    category_registry.async_create(scope="automation", name="Lights")

    with pytest.raises(HomeAssistantError, match="Nothing to update"):
        await _call(hass, "update_category", scope="automation", category_id="Lights")


async def test_update_refuses_a_rename_onto_a_taken_name(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
) -> None:
    """The registry's refusal comes back as something a user can read."""
    category_registry.async_create(scope="automation", name="Lights")
    category_registry.async_create(scope="automation", name="Heating")

    with pytest.raises(HomeAssistantError, match="already"):
        await _call(
            hass,
            "update_category",
            scope="automation",
            category_id="Heating",
            name="Lights",
        )


async def test_delete_takes_it_off_everything(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Deleting by name removes the category, and what was in it is left out."""
    category = category_registry.async_create(scope="automation", name="Lights")
    entity_id = _entity(entity_registry, "automation", "porch")
    entity_registry.async_update_entity(
        entity_id, categories={"automation": category.category_id}
    )

    await _call(hass, "delete_category", scope="automation", category_id="Lights")
    await hass.async_block_till_done()

    assert (
        category_registry.async_get_category(
            scope="automation", category_id=category.category_id
        )
        is None
    )
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.categories == {}


@pytest.mark.parametrize(
    ("domain", "scope"),
    [
        ("automation", "automation"),
        ("script", "script"),
        ("scene", "scene"),
        ("input_boolean", "helpers"),
    ],
)
async def test_add_files_the_entity_under_its_own_page(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
    entity_registry: er.EntityRegistry,
    domain: str,
    scope: str,
) -> None:
    """The scope follows from what the entity is, by name as well as by ID."""
    category = category_registry.async_create(scope=scope, name="Evening")
    entity_id = _entity(entity_registry, domain, "thing")

    await _call(
        hass, "add_category_to_entity", category_id="evening", entity_id=entity_id
    )

    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.categories == {scope: category.category_id}


async def test_add_replaces_the_category_on_that_page_only(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """One category per page: the old one there goes, others stay."""
    old = category_registry.async_create(scope="automation", name="Old")
    new = category_registry.async_create(scope="automation", name="New")
    entity_id = _entity(entity_registry, "automation", "porch")
    entity_registry.async_update_entity(
        entity_id, categories={"automation": old.category_id, "other": "kept"}
    )

    await _call(
        hass,
        "add_category_to_entity",
        category_id=new.category_id,
        entity_id=[entity_id],
    )

    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.categories == {"automation": new.category_id, "other": "kept"}


async def test_add_refuses_a_category_from_another_page(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A script category on an automation would be stored and never shown."""
    category_registry.async_create(scope="script", name="Evening")
    entity_id = _entity(entity_registry, "automation", "porch")

    with pytest.raises(HomeAssistantError, match="not found for automation"):
        await _call(
            hass, "add_category_to_entity", category_id="Evening", entity_id=entity_id
        )


@pytest.mark.parametrize(
    "service", ["add_category_to_entity", "remove_category_from_entity"]
)
async def test_an_entity_that_does_not_exist_is_refused(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
    service: str,
) -> None:
    """A typo in the entity is not a successful call that changed nothing."""
    category_registry.async_create(scope="automation", name="Lights")

    with pytest.raises(HomeAssistantError, match="not found"):
        await _call(hass, service, category_id="Lights", entity_id="automation.nope")


@pytest.mark.parametrize(
    "service", ["add_category_to_entity", "remove_category_from_entity"]
)
async def test_a_bad_entity_in_a_list_changes_none_of_them(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
    entity_registry: er.EntityRegistry,
    service: str,
) -> None:
    """An error halfway through a list leaves nothing half done."""
    lights = category_registry.async_create(scope="automation", name="Lights")
    entity_id = _entity(entity_registry, "automation", "porch")
    before = (
        {}
        if service == "add_category_to_entity"
        else {"automation": lights.category_id}
    )
    entity_registry.async_update_entity(entity_id, categories=before)

    with pytest.raises(HomeAssistantError, match="not found"):
        await _call(
            hass,
            service,
            category_id="Lights",
            entity_id=[entity_id, "automation.nope"],
        )

    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.categories == before


async def test_remove_takes_the_category_off(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The category on that page goes, the rest of the entity's stays."""
    category = category_registry.async_create(scope="automation", name="Lights")
    entity_id = _entity(entity_registry, "automation", "porch")
    entity_registry.async_update_entity(
        entity_id, categories={"automation": category.category_id, "other": "kept"}
    )

    await _call(
        hass,
        "remove_category_from_entity",
        category_id="Lights",
        entity_id=entity_id,
    )

    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.categories == {"other": "kept"}


async def test_remove_leaves_a_different_category_alone(
    hass: HomeAssistant,
    category_registry: cr.CategoryRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Asked to remove one category, it does not remove another."""
    category_registry.async_create(scope="automation", name="Lights")
    heating = category_registry.async_create(scope="automation", name="Heating")
    entity_id = _entity(entity_registry, "automation", "porch")
    entity_registry.async_update_entity(
        entity_id, categories={"automation": heating.category_id}
    )

    await _call(
        hass,
        "remove_category_from_entity",
        category_id="Lights",
        entity_id=entity_id,
    )

    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.categories == {"automation": heating.category_id}


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("update_category", {"scope": "automation", "name": "New"}),
        ("delete_category", {"scope": "automation"}),
    ],
)
async def test_a_category_that_does_not_exist_is_refused(
    hass: HomeAssistant,
    service: str,
    data: dict[str, str],
) -> None:
    """Neither the ID nor the name matching anything is an error, not a no-op."""
    with pytest.raises(HomeAssistantError, match="Category Nope not found"):
        await _call(hass, service, category_id="Nope", **data)
