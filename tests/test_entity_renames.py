"""Tests for remembering which entity IDs were renamed to what."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.util import dt as dt_util

from custom_components.spook.entity_renames import (
    DATA_ENTITY_RENAMES,
    KEEP_RENAMES_FOR,
    STORAGE_KEY,
    async_get_entity_renames,
    async_setup_entity_renames,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er


def _create(
    entity_registry: er.EntityRegistry, object_id: str, unique_id: str | None = None
) -> str:
    """Register a light and return its entity ID."""
    return entity_registry.async_get_or_create(
        "light", "hue", unique_id or object_id, suggested_object_id=object_id
    ).entity_id


def _rename(entity_registry: er.EntityRegistry, entity_id: str, new: str) -> None:
    """Rename an entity, the way the entity settings dialog does."""
    entity_registry.async_update_entity(entity_id, new_entity_id=new)


async def _written_down(hass: HomeAssistant, hass_storage: dict[str, Any]) -> Any:
    """Let the delayed save happen and return what landed on disk."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()
    return hass_storage[STORAGE_KEY]["data"]


def _renamed_to(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the entity ID Spook says this one became, if any."""
    rename = async_get_entity_renames(hass).async_renamed_to(entity_id)
    return rename.entity_id if rename else None


async def test_a_rename_is_written_down(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rename lands on disk, with when it happened."""
    freezer.move_to("2026-11-26 12:00:00+00:00")
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "kitchen"), "light.keuken")
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.kitchen") == "light.keuken"
    assert await _written_down(hass, hass_storage) == {
        "light.kitchen": {
            "entity_id": "light.keuken",
            "renamed_at": "2026-11-26T12:00:00+00:00",
        }
    }


async def test_other_updates_are_no_rename(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test changing the name or the icon writes nothing down."""
    await async_setup_entity_renames(hass)
    entity_id = _create(entity_registry, "kitchen")
    entity_registry.async_update_entity(entity_id, name="Keuken", icon="mdi:lamp")
    await hass.async_block_till_done()

    assert _renamed_to(hass, entity_id) is None


async def test_renames_in_a_row_point_at_the_last(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a reference to the first ID is pointed at where it ended up."""
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    _rename(entity_registry, "light.b", "light.c")
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") == "light.c"
    assert _renamed_to(hass, "light.b") == "light.c"


async def test_renamed_back_forgets_the_rename(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test going back to the old ID leaves nothing to point the old ID at."""
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    _rename(entity_registry, "light.b", "light.a")
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") is None
    # References written against the in-between ID do follow it back.
    assert _renamed_to(hass, "light.b") == "light.a"


async def test_an_old_id_taken_again_is_forgotten(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a new entity under the old ID ends the rename.

    The references to it work again, and are for the newcomer from then on.
    Should that one go as well, they are not the renamed entity's to have.
    """
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    newcomer = _create(entity_registry, "a", unique_id="newcomer")
    await hass.async_block_till_done()
    assert newcomer == "light.a"

    entity_registry.async_remove(newcomer)
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") is None


async def test_an_old_id_taken_by_a_rename_is_forgotten(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test another entity renamed into the old ID ends the rename too."""
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    _rename(entity_registry, _create(entity_registry, "other"), "light.a")
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") is None
    assert _renamed_to(hass, "light.other") == "light.a"


async def test_a_rename_is_kept_for_half_a_year(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rename stops counting once it is too old, and leaves the disk."""
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    await hass.async_block_till_done()
    assert set(await _written_down(hass, hass_storage)) == {"light.a"}

    freezer.tick(KEEP_RENAMES_FOR - timedelta(minutes=2))
    assert _renamed_to(hass, "light.a") == "light.b"

    freezer.tick(timedelta(minutes=3))
    assert _renamed_to(hass, "light.a") is None

    # Gone from the disk with the next write.
    _rename(entity_registry, _create(entity_registry, "x"), "light.y")
    await hass.async_block_till_done()
    assert set(await _written_down(hass, hass_storage)) == {"light.x"}


async def test_the_clock_runs_from_the_first_rename(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a later rename does not make an old broken reference young again."""
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    await hass.async_block_till_done()

    freezer.tick(KEEP_RENAMES_FOR - timedelta(days=1))
    _rename(entity_registry, "light.b", "light.c")
    await hass.async_block_till_done()

    freezer.tick(timedelta(days=2))
    assert _renamed_to(hass, "light.a") is None
    assert _renamed_to(hass, "light.b") == "light.c"


async def test_too_old_on_disk_is_dropped_on_load(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test what was too old by the time Home Assistant came back is let go."""
    freezer.move_to("2026-11-26 12:00:00+00:00")
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": {
            "light.old": {
                "entity_id": "light.new",
                "renamed_at": "2026-01-01T00:00:00+00:00",
            },
            "light.recent": {
                "entity_id": "light.newer",
                "renamed_at": "2026-11-01T00:00:00+00:00",
            },
            "light.broken": {"entity_id": "light.what"},
        },
    }
    await async_setup_entity_renames(hass)

    assert _renamed_to(hass, "light.old") is None
    assert _renamed_to(hass, "light.recent") == "light.newer"
    assert _renamed_to(hass, "light.broken") is None
    assert set(await _written_down(hass, hass_storage)) == {"light.recent"}


async def test_a_rename_survives_a_restart(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test the rename is on disk, not only in memory."""
    unload = await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    await hass.async_block_till_done()
    await _written_down(hass, hass_storage)

    unload()
    hass.data.pop(DATA_ENTITY_RENAMES)
    await async_setup_entity_renames(hass)

    assert _renamed_to(hass, "light.a") == "light.b"


async def test_a_reload_before_it_is_written_loses_nothing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test reloading Spook inside the save delay keeps the latest rename."""
    unload = await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    await hass.async_block_till_done()

    unload()
    await async_setup_entity_renames(hass)

    assert _renamed_to(hass, "light.a") == "light.b"
    assert set(await _written_down(hass, hass_storage)) == {"light.a"}


async def test_unloaded_sees_no_renames(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test nothing is followed once Spook is unloaded."""
    unload = await async_setup_entity_renames(hass)
    unload()
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") is None
