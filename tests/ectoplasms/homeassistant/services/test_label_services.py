"""Tests for the label actions saying what they could not find."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.ectoplasms.homeassistant.services import (
    add_label_to_area,
    add_label_to_device,
    add_label_to_entity,
    remove_label_from_area,
    remove_label_from_device,
    remove_label_from_entity,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        area_registry as ar,
        entity_registry as er,
        label_registry as lr,
    )

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
