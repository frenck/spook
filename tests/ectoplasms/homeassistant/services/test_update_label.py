"""Tests for the homeassistant.update_label action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.ectoplasms.homeassistant.services import update_label

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        entity_registry as er,
        label_registry as lr,
    )


async def _setup(hass: HomeAssistant) -> None:
    """Register the action."""
    assert await async_setup_component(hass, "homeassistant", {})
    update_label.SpookService(hass).async_register()
    await hass.async_block_till_done()


async def _update(hass: HomeAssistant, **data: object) -> None:
    """Call the action."""
    await hass.services.async_call(
        "homeassistant", "update_label", dict(data), blocking=True
    )


async def test_it_leaves_alone_what_the_call_did_not_mention(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
) -> None:
    """The reason this action exists at all.

    Somebody updating a description wants the icon, colour and name they
    already picked to survive it. Passing every field through would read an
    unmentioned icon as "remove the icon".
    """
    label = label_registry.async_create(
        "Ghosts", color="red", description="Old", icon="mdi:ghost"
    )
    await _setup(hass)

    await _update(hass, label_id=label.label_id, description="New")

    updated = label_registry.async_get_label(label.label_id)
    assert updated.description == "New"
    assert updated.name == "Ghosts"
    assert updated.color == "red"
    assert updated.icon == "mdi:ghost"


async def test_it_keeps_the_label_on_everything_it_was_on(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Editing used to mean deleting and recreating.

    That took the label off every entity and device carrying it, which is why
    this was asked for in the first place.
    """
    label = label_registry.async_create("Ghosts", description="Old")
    entry = entity_registry.async_get_or_create("light", "test", "1")
    entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})
    await _setup(hass)

    await _update(hass, label_id=label.label_id, description="New")

    assert entity_registry.async_get(entry.entity_id).labels == {label.label_id}


async def test_a_label_that_does_not_exist_is_refused(
    hass: HomeAssistant,
) -> None:
    """Core raises a bare KeyError on this, which surfaces as an unknown error."""
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match=r"Label .* not found"):
        await _update(hass, label_id="no_such_label", name="Ghosts")


async def test_a_call_that_changes_nothing_is_refused(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
) -> None:
    """A misspelled field name would otherwise be a successful no-op.

    The automation that made the call carries on as though it had renamed
    something, and nothing anywhere says it did not.
    """
    label = label_registry.async_create("Ghosts")
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match="Nothing to update"):
        await _update(hass, label_id=label.label_id)
