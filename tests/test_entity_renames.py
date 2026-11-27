"""Tests for remembering which entity IDs were renamed to what."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
import logging

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from custom_components.spook.entity_renames import (
    DATA_ENTITY_RENAMES,
    KEEP_RENAMES_FOR,
    STORAGE_KEY,
    EntityRenames,
    async_get_entity_renames,
    async_setup_entity_renames,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import Event, HomeAssistant


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
    """Have the pending save go out and return what landed on disk.

    Through the final write Home Assistant does on its way down. Moving the
    clock is not enough: a save asked for twice before it went out checks
    the loop's own clock, which the tests do not move.
    """
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
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
            "registry_id": entity_registry.async_get("light.keuken").id,
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
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test what was too old by the time Home Assistant came back is let go."""
    freezer.move_to("2026-11-26 12:00:00+00:00")
    new = entity_registry.async_get(_create(entity_registry, "new"))
    newer = entity_registry.async_get(_create(entity_registry, "newer"))
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": {
            "light.old": {
                "entity_id": "light.new",
                "registry_id": new.id,
                "renamed_at": "2026-01-01T00:00:00+00:00",
            },
            "light.recent": {
                "entity_id": "light.newer",
                "registry_id": newer.id,
                "renamed_at": "2026-11-01T00:00:00+00:00",
            },
            "light.broken": {"entity_id": "light.newer"},
        },
    }
    await async_setup_entity_renames(hass)

    assert _renamed_to(hass, "light.old") is None
    assert _renamed_to(hass, "light.recent") == "light.newer"
    assert _renamed_to(hass, "light.broken") is None
    assert set(await _written_down(hass, hass_storage)) == {"light.recent"}


async def test_a_stranger_under_the_new_id_is_not_pointed_at(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a different entity taking the new ID ends the rename.

    The renamed entity was removed, and something else got its name. The
    references to the old ID were never written for that one, here or
    wherever it gets renamed to next.
    """
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    entity_registry.async_remove("light.b")
    stranger = _create(entity_registry, "b", unique_id="stranger")
    await hass.async_block_till_done()
    assert stranger == "light.b"

    assert _renamed_to(hass, "light.a") is None

    _rename(entity_registry, stranger, "light.c")
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") is None
    assert _renamed_to(hass, "light.b") == "light.c"


async def test_a_stranger_renamed_into_the_new_id_is_not_pointed_at(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a different entity renamed into the new ID ends the rename too."""
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    entity_registry.async_remove("light.b")
    _rename(entity_registry, _create(entity_registry, "stranger"), "light.b")
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") is None
    assert _renamed_to(hass, "light.stranger") == "light.b"


async def test_the_renamed_entity_coming_back_keeps_the_rename(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the same entity removed and added again is still pointed at.

    Like an integration removed and added again: Home Assistant gives the
    entity its old registry entry back, and with it its ID.
    """
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    entity_registry.async_remove("light.b")
    await hass.async_block_till_done()

    # Gone for now: nothing to point at.
    assert _renamed_to(hass, "light.a") is None

    assert _create(entity_registry, "a") == "light.b"
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") == "light.b"


async def test_an_old_id_taken_while_unloaded_is_forgotten(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test an old ID taken while Spook was off is caught up on at setup.

    Nobody heard the newcomer arrive. Should it leave again, the references
    to its ID are not the renamed entity's to have.
    """
    unload = await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    _rename(entity_registry, _create(entity_registry, "x"), "light.y")
    await hass.async_block_till_done()

    unload()
    newcomer = _create(entity_registry, "a", unique_id="newcomer")
    assert newcomer == "light.a"
    await async_setup_entity_renames(hass)

    entity_registry.async_remove(newcomer)
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") is None
    assert _renamed_to(hass, "light.x") == "light.y"
    assert set(await _written_down(hass, hass_storage)) == {"light.x"}


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


def _stored_rename(registry_id: str, entity_id: str = "light.b") -> dict[str, str]:
    """Return a rename the way Spook writes one down."""
    return {
        "entity_id": entity_id,
        "registry_id": registry_id,
        "renamed_at": "2026-11-01T00:00:00+00:00",
    }


@pytest.mark.parametrize(
    "stored",
    [
        ["light.a", "light.b"],
        "light.a",
        42,
    ],
)
async def test_a_store_that_is_not_a_mapping_starts_empty(
    hass: HomeAssistant,
    stored: Any,
) -> None:
    """Test a store holding something else entirely is let go."""
    renames = EntityRenames(hass, None, stored)

    assert renames.async_renamed_to("light.a") is None


@pytest.mark.parametrize(
    "broken",
    [
        "light.b",
        ["light.b"],
        None,
        {"entity_id": 5, "registry_id": "abc", "renamed_at": "2026-11-01T00:00:00Z"},
        {"entity_id": "light.b", "registry_id": ["abc"]},
        {"entity_id": "light.b", "registry_id": "abc", "renamed_at": 1764000000},
        {"entity_id": "light.b", "registry_id": "abc", "renamed_at": None},
        {"entity_id": "light.b", "registry_id": "abc", "renamed_at": "yesterday"},
        {
            "entity_id": "light.b",
            "registry_id": "abc",
            "renamed_at": "2026-02-30T00:00:00+00:00",
        },
        {
            "entity_id": "light.b",
            "registry_id": "abc",
            "renamed_at": "2026-11-01T25:00:00+00:00",
        },
        {
            "entity_id": "light.b",
            "registry_id": "abc",
            "renamed_at": "9999-12-31T24:00:00+00:00",
        },
        {"entity_id": "", "registry_id": "abc", "renamed_at": "2026-11-01T00:00:00Z"},
    ],
)
async def test_a_row_that_makes_no_sense_is_dropped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    broken: Any,
) -> None:
    """Test a damaged row goes, and the rest is kept.

    The file can be edited by hand or come back from an old backup. Whatever
    is in it, Spook has to set up.
    """
    freezer.move_to("2026-11-26 12:00:00+00:00")
    caplog.set_level(logging.DEBUG, logger="custom_components.spook")
    entry = entity_registry.async_get(_create(entity_registry, "c"))

    renames = EntityRenames(
        hass,
        None,
        {"light.broken": broken, "light.a": _stored_rename(entry.id, "light.c")},
    )

    assert renames.async_renamed_to("light.broken") is None
    assert renames.async_renamed_to("light.a").entity_id == "light.c"

    # How many, not which: entity IDs are the user's.
    assert "dropped 1 entity renames" in caplog.text
    assert "light.broken" not in caplog.text


async def test_a_key_that_is_not_an_entity_id_is_dropped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a row filed under something other than a string goes.

    JSON only has strings for keys, but what comes in is not always JSON,
    and the next save sorts by the key.
    """
    freezer.move_to("2026-11-26 12:00:00+00:00")
    entry = entity_registry.async_get(_create(entity_registry, "c"))

    renames = EntityRenames(
        hass,
        None,
        {5: _stored_rename(entry.id, "light.c"), "light.a": _stored_rename(entry.id)},
    )

    assert renames.async_renamed_to(5) is None  # type: ignore[arg-type]
    assert renames._data_to_save().keys() == {"light.a"}  # noqa: SLF001  # pylint: disable=protected-access


async def test_a_time_without_a_zone_is_read_as_utc(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rename written down without a time zone is kept, in UTC.

    Spook writes UTC, so that is the closest guess at one with the zone lost.
    Wrong by a few hours at worst, on a window of half a year, where dropping
    it would lose the lead altogether.
    """
    freezer.move_to("2026-11-26 12:00:00+00:00")
    entry = entity_registry.async_get(_create(entity_registry, "c"))
    recent = _stored_rename(entry.id, "light.c") | {"renamed_at": "2026-11-01T00:00:00"}
    too_old = _stored_rename(entry.id, "light.c") | {
        "renamed_at": "2026-01-01T00:00:00"
    }

    renames = EntityRenames(hass, None, {"light.a": recent, "light.old": too_old})

    rename = renames.async_renamed_to("light.a")
    assert rename is not None
    assert rename.renamed_at == datetime(2026, 11, 1, tzinfo=UTC)
    assert renames.async_renamed_to("light.old") is None


async def test_a_damaged_store_does_not_stop_setting_up(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the rename log sets up from a damaged file, keeping what is sound."""
    freezer.move_to("2026-11-26 12:00:00+00:00")
    entry = entity_registry.async_get(_create(entity_registry, "c"))
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": {
            "light.a": _stored_rename(entry.id, "light.c"),
            "light.string": "light.c",
            "light.nothing": None,
            "light.naive": _stored_rename(entry.id, "light.c")
            | {"renamed_at": "2026-11-02T00:00:00"},
            "light.number": _stored_rename(entry.id, "light.c")
            | {"renamed_at": 1764000000},
        },
    }

    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "x"), "light.y")
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") == "light.c"
    assert _renamed_to(hass, "light.naive") == "light.c"
    assert set(await _written_down(hass, hass_storage)) == {
        "light.a",
        "light.naive",
        "light.x",
    }


async def test_a_store_holding_a_list_does_not_stop_setting_up(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test the rename log sets up from a file that holds a list."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": ["light.a", "light.b"],
    }

    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    await hass.async_block_till_done()

    assert _renamed_to(hass, "light.a") == "light.b"
    assert set(await _written_down(hass, hass_storage)) == {"light.a"}


async def _restart(
    hass: HomeAssistant, unload: Callable[[], None]
) -> Callable[[], None]:
    """Stop following renames and start again from what is on disk."""
    unload()
    hass.data.pop(DATA_ENTITY_RENAMES)
    return await async_setup_entity_renames(hass)


async def test_an_old_id_taken_again_is_forgotten_after_a_restart(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test a newcomer under the old ID ends the rename on disk too.

    Gone again before the restart, nothing at setup can tell it was ever
    there. Only what was written when it arrived can.
    """
    unload = await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    await hass.async_block_till_done()
    await _written_down(hass, hass_storage)

    newcomer = _create(entity_registry, "a", unique_id="newcomer")
    await hass.async_block_till_done()
    await _written_down(hass, hass_storage)
    entity_registry.async_remove(newcomer)
    await hass.async_block_till_done()

    await _restart(hass, unload)

    assert _renamed_to(hass, "light.a") is None


async def test_an_old_id_taken_while_unloaded_is_forgotten_on_disk_too(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test catching up at setup is written down, not only done in memory.

    The newcomer gone again before the next restart, that setup has nothing
    left to catch up on.
    """
    unload = await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    await hass.async_block_till_done()
    await _written_down(hass, hass_storage)

    unload()
    hass.data.pop(DATA_ENTITY_RENAMES)
    newcomer = _create(entity_registry, "a", unique_id="newcomer")
    unload = await async_setup_entity_renames(hass)
    await _written_down(hass, hass_storage)
    entity_registry.async_remove(newcomer)
    await hass.async_block_till_done()

    await _restart(hass, unload)

    assert _renamed_to(hass, "light.a") is None


async def test_a_rename_of_an_entity_already_gone_is_let_go(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a rename whose entity left before Spook heard of it is let go.

    Another listener can remove it the moment it is renamed. Spook hears of
    the rename after that, with nothing left to point at.
    """

    @callback
    def _remove_on_rename(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Remove the entity as soon as it is renamed."""
        if "old_entity_id" in event.data:
            entity_registry.async_remove(event.data["entity_id"])

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _remove_on_rename)
    await async_setup_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    await hass.async_block_till_done()

    assert entity_registry.async_get("light.b") is None
    assert _renamed_to(hass, "light.a") is None


async def test_without_spook_set_up_nothing_is_written_down(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test a repair looking without Spook set up gets an empty set.

    One that follows nothing and never goes to disk.
    """
    renames = async_get_entity_renames(hass)
    _rename(entity_registry, _create(entity_registry, "a"), "light.b")
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()

    assert not renames.is_written_down
    assert async_get_entity_renames(hass) is renames
    assert _renamed_to(hass, "light.a") is None
    assert STORAGE_KEY not in hass_storage
