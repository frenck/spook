"""Tests for the proof Spook asks for before it removes a reference.

The fix buttons lean on what Home Assistant's entity registry does with an
entity it deletes, so that is pinned here too, against the real registry: a
change in core that moves the premise should fail here, not in somebody's
house.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.helpers import entity_registry as er

from custom_components.spook.entity_filtering import async_get_deleted_entities
from custom_components.spook.removal_evidence import (
    async_deleted_entry,
    async_removed_on_purpose,
)

from tests.repair_helpers import (
    async_add_config_entry,
    async_delete_entity,
    async_disable_config_entry,
    async_forget_deleted_entities,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant


async def test_an_entity_deleted_from_the_registry_is_proof(
    hass: HomeAssistant,
) -> None:
    """Test an entity the registry removed has the record to show for it."""
    async_delete_entity(hass, "sensor.gone")

    assert async_removed_on_purpose(hass, ["sensor.gone"]) == {"sensor.gone"}
    assert async_deleted_entry(hass, "sensor.gone")


async def test_an_entity_that_was_never_registered_is_no_proof(
    hass: HomeAssistant,
) -> None:
    """Test absence alone proves nothing.

    A YAML sensor without a unique ID that has not come up yet has no state
    and no registry entry, and no record of being deleted either.
    """
    assert async_removed_on_purpose(hass, ["sensor.not_up_yet"]) == set()


async def test_a_disabled_entity_is_not_deleted(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabling an entity keeps it registered, and out of the record."""
    entry = entity_registry.async_get_or_create("sensor", "demo", "disabled")
    entity_registry.async_update_entity(
        entry.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )

    assert entity_registry.deleted_entities == {}
    assert async_removed_on_purpose(hass, [entry.entity_id]) == set()


async def test_an_entity_of_an_unloaded_integration_is_not_deleted(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an integration being disabled and unloaded keeps its entities.

    The same goes for one failing to set up, or retrying: the entities stay
    in the registry until the integration itself is removed.
    """
    config_entry = async_add_config_entry(hass, "demo")
    await hass.config_entries.async_setup(config_entry.entry_id)
    entry = entity_registry.async_get_or_create(
        "sensor", "demo", "unloaded", config_entry=config_entry
    )

    await async_disable_config_entry(hass, config_entry)

    assert entity_registry.async_get(entry.entity_id)
    assert async_removed_on_purpose(hass, [entry.entity_id]) == set()


async def test_an_entity_of_a_removed_integration_is_proof(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing the integration puts its entities on the record."""
    config_entry = MockConfigEntry(domain="demo")
    config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        "sensor", "demo", "removed", config_entry=config_entry
    )

    await hass.config_entries.async_remove(config_entry.entry_id)

    assert async_removed_on_purpose(hass, [entry.entity_id]) == {entry.entity_id}


async def test_an_entity_that_came_back_is_no_longer_proof(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entity registered again under its unique ID leaves the record."""
    async_delete_entity(hass, "sensor.back")

    entity_registry.async_get_or_create(
        "sensor", "spook_test", "back", suggested_object_id="back"
    )

    assert entity_registry.deleted_entities == {}
    assert async_removed_on_purpose(hass, ["sensor.back"]) == set()


async def test_another_entity_under_the_deleted_id_is_no_proof(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a different entity taking the entity ID is not the deleted one."""
    async_delete_entity(hass, "sensor.taken")

    entity_registry.async_get_or_create(
        "sensor", "other", "newcomer", suggested_object_id="taken"
    )

    assert async_removed_on_purpose(hass, ["sensor.taken"]) == set()


async def test_home_assistant_forgetting_a_deleted_entity_ends_the_proof(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the record is asked for as it is, not as Spook last read it.

    Home Assistant forgets a deleted entity nothing owns after a month, and
    says nothing when it does. Spook's own map of deleted entities still
    names it afterwards.
    """
    async_delete_entity(hass, "sensor.gone")
    assert "sensor.gone" in async_get_deleted_entities(hass)

    async_forget_deleted_entities(hass, freezer)

    assert "sensor.gone" in async_get_deleted_entities(hass)
    assert async_removed_on_purpose(hass, ["sensor.gone"]) == set()


async def test_a_deleted_entity_of_an_integration_still_there_is_kept(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the month only starts once nothing owns the deleted entity."""
    config_entry = MockConfigEntry(domain="demo")
    config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        "sensor", "demo", "kept", config_entry=config_entry
    )
    entity_registry.async_remove(entry.entity_id)

    async_forget_deleted_entities(hass, freezer)

    assert async_removed_on_purpose(hass, [entry.entity_id]) == {entry.entity_id}


async def test_a_registry_id_that_no_longer_resolves_is_proof(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an entity registry ID leading nowhere is proof on its own.

    Only a registered entity is ever handed one, so even once Home Assistant
    forgot deleting it, it was there.
    """
    deleted = async_delete_entity(hass, "sensor.gone")
    live = entity_registry.async_get_or_create("sensor", "demo", "live")

    proven_while_remembered = async_removed_on_purpose(hass, [deleted.id, live.id])
    async_forget_deleted_entities(hass, freezer)
    proven_once_forgotten = async_removed_on_purpose(hass, [deleted.id])

    assert proven_while_remembered == {deleted.id}
    assert proven_once_forgotten == {deleted.id}


async def test_something_not_shaped_like_a_registry_id_is_no_proof(
    hass: HomeAssistant,
) -> None:
    """Test a typo that resolves to nothing is not taken for a registry ID."""
    assert async_removed_on_purpose(hass, ["not-a-registry-id"]) == set()
