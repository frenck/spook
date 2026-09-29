"""Tests for the label actions saying what they could not find."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.ectoplasms.homeassistant.services import (
    add_label_to_area,
    add_label_to_device,
    add_label_to_entity,
    create_label,
    remove_label_from_area,
    remove_label_from_device,
    remove_label_from_entity,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import label_registry as lr

_ADD = (add_label_to_entity, add_label_to_area, add_label_to_device)
_REMOVE = (remove_label_from_entity, remove_label_from_area, remove_label_from_device)
_FIELD = {
    "add_label_to_entity": "entity_id",
    "remove_label_from_entity": "entity_id",
    "add_label_to_area": "area_id",
    "remove_label_from_area": "area_id",
    "add_label_to_device": "device_id",
    "remove_label_from_device": "device_id",
}


async def _setup(hass: HomeAssistant, module: object) -> None:
    """Register one label action."""
    assert await async_setup_component(hass, "homeassistant", {})
    module.SpookService(hass).async_register()  # type: ignore[attr-defined]
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "module", [*_ADD, *_REMOVE], ids=lambda m: m.__name__.rsplit(".", 1)[-1]
)
async def test_a_target_that_does_not_exist_is_refused(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
    module: object,
) -> None:
    """A typo in the target used to come back as a successful no-op.

    Which means an automation carries on as though it had labelled something,
    and nothing anywhere says otherwise.
    """
    label_registry.async_create("Ghosts")
    await _setup(hass, module)

    service = module.SpookService  # type: ignore[attr-defined]
    field = _FIELD[module.__name__.rsplit(".", 1)[-1]]

    with pytest.raises(HomeAssistantError, match="not found"):
        await hass.services.async_call(
            "homeassistant",
            service.service,
            {"label_id": "ghosts", field: "does.not_exist"},
            blocking=True,
        )


@pytest.mark.parametrize("module", _REMOVE, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
async def test_a_label_that_does_not_exist_is_refused_on_removal_too(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    module: object,
) -> None:
    """The adding half already said so; removal stayed quiet about it.

    A typo there leaves the label everybody meant to remove exactly where it
    was, and the call still reports success.
    """
    await _setup(hass, module)

    entry = entity_registry.async_get_or_create("light", "test", "1")
    area = area_registry.async_create("Kitchen")
    targets = {
        "entity_id": entry.entity_id,
        "area_id": area.id,
        "device_id": "does_not_matter",
    }

    service = module.SpookService  # type: ignore[attr-defined]
    field = _FIELD[module.__name__.rsplit(".", 1)[-1]]

    with pytest.raises(HomeAssistantError, match=r"Label .* not found"):
        await hass.services.async_call(
            "homeassistant",
            service.service,
            {"label_id": "no_such_label", field: targets[field]},
            blocking=True,
        )


def _labels_of(hass: HomeAssistant, field: str, target: str) -> set[str]:
    """Return the labels on an entity, area, or device."""
    if field == "entity_id":
        entry = er.async_get(hass).async_get(target)
    elif field == "area_id":
        entry = ar.async_get(hass).async_get_area(target)
    else:
        entry = dr.async_get(hass).async_get(target)
    assert entry is not None
    return set(entry.labels)


def _labelled_target(hass: HomeAssistant, field: str, labels: set[str]) -> str:
    """Create an entity, area, or device carrying these labels."""
    if field == "entity_id":
        registry = er.async_get(hass)
        target = registry.async_get_or_create("light", "test", "1").entity_id
        registry.async_update_entity(target, labels=labels)
        return target

    if field == "area_id":
        area = ar.async_get(hass).async_create("Kitchen")
        ar.async_get(hass).async_update(area.id, labels=labels)
        return area.id

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "1")}
    )
    dr.async_get(hass).async_update_device(device.id, labels=labels)
    return device.id


@pytest.mark.parametrize(
    "module", [*_ADD, *_REMOVE], ids=lambda m: m.__name__.rsplit(".", 1)[-1]
)
async def test_a_bad_target_in_a_list_changes_none_of_them(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
    module: object,
) -> None:
    """An error halfway through a list leaves nothing half done.

    The first target used to be changed before the second one turned out not
    to exist, so the automation reported a failure with half the work done.
    """
    label_registry.async_create("Ghosts")
    await _setup(hass, module)

    name = module.__name__.rsplit(".", 1)[-1]
    field = _FIELD[name]
    before = set() if name.startswith("add_") else {"ghosts"}
    target = _labelled_target(hass, field, before)

    service = module.SpookService  # type: ignore[attr-defined]
    with pytest.raises(HomeAssistantError, match="not found"):
        await hass.services.async_call(
            "homeassistant",
            service.service,
            {"label_id": "ghosts", field: [target, "does_not_exist"]},
            blocking=True,
        )

    assert _labels_of(hass, field, target) == before


async def test_creating_a_label_whose_name_is_taken_says_so(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
) -> None:
    """Core refuses this with a bare ValueError, not a second label.

    Unconverted it reaches the caller as an unknown error, which is a poor
    description of a name collision.
    """
    label_registry.async_create("Ghosts")
    await _setup(hass, create_label)

    with pytest.raises(HomeAssistantError, match="already in use"):
        await hass.services.async_call(
            "homeassistant", "create_label", {"name": "Ghosts"}, blocking=True
        )
