"""Spook - Your homie. Remembering which entity IDs were renamed to what."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, TypedDict

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant

STORAGE_KEY = f"{DOMAIN}.entity_renames"
STORAGE_VERSION = 1

# Renames come one at a time, somebody typing in a dialog. Waiting a few
# seconds costs nothing, and Home Assistant writes what is pending on its
# way down anyway.
_SAVE_DELAY = 5

# A rename is a good lead for a while and then it is not. Half a year on, a
# reference to the old ID is something nobody missed, or something already
# put right by hand, and pointing at whatever carries the name now is
# guessing with more confidence than it deserves.
KEEP_RENAMES_FOR = timedelta(days=180)

DATA_ENTITY_RENAMES: HassKey[EntityRenames] = HassKey("spook_entity_renames")


class _StoredRename(TypedDict):
    """A rename the way it goes on disk."""

    entity_id: str
    registry_id: str
    renamed_at: str


@dataclass(frozen=True, slots=True)
class EntityRename:
    """What an entity ID was renamed to, and when.

    With the entity registry ID of the entity that was renamed. The entity ID
    is a name, and another entity can take it. The registry ID is the entity:
    it stays through renames, and an entity that is removed and comes back,
    like an integration added again, gets it back.
    """

    entity_id: str
    registry_id: str
    renamed_at: datetime


def _read_stored_rename(stored: object) -> EntityRename | None:
    """Return a rename read back from disk, or None if it makes no sense."""
    if not isinstance(stored, Mapping):
        return None

    entity_id = stored.get("entity_id")
    registry_id = stored.get("registry_id")
    renamed_at = stored.get("renamed_at")
    if not (
        isinstance(entity_id, str)
        and entity_id
        and isinstance(registry_id, str)
        and registry_id
        and isinstance(renamed_at, str)
    ):
        return None

    # Text that is no time at all comes back as nothing. A time that cannot
    # be raises instead: the thirtieth of February as a `ValueError`, and
    # midnight at the end of the last day of the calendar as an
    # `OverflowError`.
    try:
        when = dt_util.parse_datetime(renamed_at)
    except ValueError, OverflowError:
        return None

    if when is None:
        return None

    # Spook writes UTC, so that is the best guess for a time that lost its
    # zone. A few hours off at worst, on a window of half a year, where
    # dropping it would lose the lead altogether.
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt_util.UTC)

    return EntityRename(entity_id, registry_id, when)


class EntityRenames:
    """The entity IDs renamed in the entity registry, by the ID they had.

    Home Assistant says an entity was renamed once, in the event the moment it
    happens, and forgets it right after. The registry only knows the new ID.
    So the old one is written down here, for the references still using it.

    Only what happened while Spook was there to see it. A rename from before,
    or from while Spook was off, is not in here and never will be.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        store: Store[dict[str, _StoredRename]] | None = None,
        stored: Mapping[str, _StoredRename] | None = None,
    ) -> None:
        """Hold what was loaded, minus what is too old to keep."""
        self._hass = hass
        self._store = store
        self._renames: dict[str, EntityRename] = {}

        # The file can be edited by hand, or come back from an old backup.
        # Whatever is in it, Spook sets up: what makes no sense goes, the
        # rest is kept.
        if stored is None:
            stored = {}
        elif not isinstance(stored, Mapping):
            LOGGER.debug("Spook could not read its entity renames, starting over")
            stored = {}

        for old_entity_id, stored_rename in stored.items():
            if isinstance(old_entity_id, str) and old_entity_id:
                rename = _read_stored_rename(stored_rename)
                if rename is not None:
                    self._renames[old_entity_id] = rename

        if dropped := len(stored) - len(self._renames):
            LOGGER.debug("Spook dropped %s entity renames it could not read", dropped)

        if self._async_forget_old():
            self._async_schedule_save()

    @property
    def is_written_down(self) -> bool:
        """Return whether this is the copy that goes to disk."""
        return self._store is not None

    @callback
    def async_renamed_to(self, entity_id: str) -> EntityRename | None:
        """Return what this entity ID was renamed to, if it was, recently.

        The ID it ends up at, after however many renames since. Only while the
        entity carrying that ID is the one that was renamed. Gone, or another
        entity under that name, and there is nothing to point at.
        """
        if (rename := self._renames.get(entity_id)) is None:
            return None

        if rename.renamed_at < dt_util.utcnow() - KEEP_RENAMES_FOR:
            return None

        entry = er.async_get(self._hass).async_get(rename.entity_id)
        if entry is None or entry.id != rename.registry_id:
            return None

        return rename

    @callback
    def async_entity_registry_updated(
        self,
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Write down a rename, or forget one that no longer holds."""
        data = event.data
        if data["action"] == "create":
            if self._async_taken(data["entity_id"]):
                self._async_schedule_save()
            return

        if data["action"] != "update" or "old_entity_id" not in data:
            return

        if (entry := er.async_get(self._hass).async_get(data["entity_id"])) is None:
            return

        self._async_renamed(data["old_entity_id"], data["entity_id"], entry.id)

    @callback
    def _async_renamed(
        self, old_entity_id: str, new_entity_id: str, registry_id: str
    ) -> None:
        """Write down that one entity ID became another."""
        # Renamed back to what it once was ends up here too: nothing to point
        # at any more, the old references work again.
        self._async_taken(new_entity_id)

        # When it was renamed is when the references to it broke, and that is
        # what the clock runs from. A rename further down the line moves where
        # they should point, not how long they have been pointing nowhere.
        #
        # Followed by the entity, not by its name. A stranger that took the ID
        # an earlier rename went to is not the entity those references are for,
        # and neither is wherever it is renamed to next.
        for earlier_id, earlier in list(self._renames.items()):
            if earlier.registry_id != registry_id:
                continue

            self._renames[earlier_id] = EntityRename(
                new_entity_id, registry_id, earlier.renamed_at
            )

        self._renames[old_entity_id] = EntityRename(
            new_entity_id, registry_id, dt_util.utcnow()
        )
        self._async_schedule_save()

    @callback
    def _async_taken(self, entity_id: str) -> bool:
        """Forget a rename away from an ID that something carries again.

        A reference to it works again, and whatever it is written for now is
        not the entity that left. Should the newcomer go too, its references
        are not the renamed one's to have.

        A stranger taking the ID a rename went to is left alone here. The
        lookup sees it is not the renamed entity, and should that one come
        back under its name, the rename holds again.
        """
        return self._renames.pop(entity_id, None) is not None

    @callback
    def async_forget_taken(self) -> None:
        """Forget the renames away from IDs that are in the registry again.

        For what happened while nobody was listening. An entity created under
        an old ID while Spook was off sent its event to no one, and should it
        leave again later, the references to that ID are not the renamed
        entity's to have.
        """
        registry = er.async_get(self._hass)
        taken = [
            old_entity_id
            for old_entity_id in self._renames
            if registry.async_get(old_entity_id) is not None
        ]
        for old_entity_id in taken:
            del self._renames[old_entity_id]

        if taken:
            self._async_schedule_save()

    @callback
    def _async_forget_old(self) -> bool:
        """Drop the renames too old to keep. Return whether any went."""
        cutoff = dt_util.utcnow() - KEEP_RENAMES_FOR
        too_old = [
            old_entity_id
            for old_entity_id, rename in self._renames.items()
            if rename.renamed_at < cutoff
        ]
        for old_entity_id in too_old:
            del self._renames[old_entity_id]

        return bool(too_old)

    async def async_remove(self) -> None:
        """Remove what is on disk, and never write it again.

        A save still waiting would put the file back, a few seconds later or
        on the way down. Removing through the same store calls that off.
        """
        store, self._store = self._store, None
        if store is None:
            return

        # Saving waits for a write that is under way, and leaves none behind.
        # Not every Home Assistant that Spook runs on waits for one before it
        # removes the file, and a write landing after would put the file back.
        await store.async_save(self._data_to_save())
        await store.async_remove()

    @callback
    def _async_schedule_save(self) -> None:
        """Write it down, soon."""
        if self._store is not None:
            self._store.async_delay_save(self._data_to_save, _SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, _StoredRename]:
        """Return what goes on disk."""
        self._async_forget_old()
        return {
            old_entity_id: {
                "entity_id": rename.entity_id,
                "registry_id": rename.registry_id,
                "renamed_at": rename.renamed_at.isoformat(),
            }
            for old_entity_id, rename in sorted(self._renames.items())
        }


@callback
def async_get_entity_renames(hass: HomeAssistant) -> EntityRenames:
    """Return the renames, or an empty set that is never written down.

    The empty set is for a repair asked to look without Spook having been set
    up around it, which is a test and not a house.
    """
    if (renames := hass.data.get(DATA_ENTITY_RENAMES)) is None:
        renames = hass.data[DATA_ENTITY_RENAMES] = EntityRenames(hass)

    return renames


async def async_setup_entity_renames(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Load the renames seen before, and follow the ones from now on.

    Loaded once and then kept, reloads included, for the same reason as the
    dismissals: a reload inside the save delay that read the disk again would
    start from before the latest rename, and two copies writing their own
    idea of it would lose one.
    """
    renames = hass.data.get(DATA_ENTITY_RENAMES)
    if renames is None or not renames.is_written_down:
        store: Store[dict[str, _StoredRename]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        renames = hass.data[DATA_ENTITY_RENAMES] = EntityRenames(
            hass, store, await store.async_load()
        )

    # Kept across a reload too, and Spook can be off for a while in between.
    renames.async_forget_taken()

    return hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        renames.async_entity_registry_updated,
    )


async def async_remove_entity_renames(hass: HomeAssistant) -> None:
    """Remove the renames, on disk too, for Spook being removed.

    Out of `hass.data` as well, so Spook added again in the same run starts
    from nothing rather than from what was kept across reloads.
    """
    renames = hass.data.pop(DATA_ENTITY_RENAMES, None)
    if renames is not None and renames.is_written_down:
        await renames.async_remove()
        return

    # Not loaded in this run, like Spook disabled before the restart. The
    # file is still there.
    await Store(hass, STORAGE_VERSION, STORAGE_KEY).async_remove()
