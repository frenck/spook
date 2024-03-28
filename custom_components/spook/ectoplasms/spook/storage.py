"""Spook - Not your homie."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, TypedDict

from homeassistant.core import callback
from homeassistant.helpers.storage import Store

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_SENTINEL = object()

STORAGE_KEY = "spook_key_value_store"
STORAGE_MAJOR_VERSION = 1
STORAGE_MINOR_VERSION = 1


class SpookKeyValueStoreItem(TypedDict):
    """Spook key/value store item."""

    key: str
    last_modified: datetime | None
    is_persistent: bool
    ttl: int | None
    value: Any


class SpookKeyValueStore:
    """Key/Value storage for Spook."""

    _persistent_storage: Store[str, SpookKeyValueStoreItem]
    _store: dict[str, SpookKeyValueStoreItem]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Spook key/value store."""
        self._hass = hass
        self._persistent_storage = Store(
            hass,
            key=STORAGE_KEY,
            version=STORAGE_MAJOR_VERSION,
            minor_version=STORAGE_MINOR_VERSION,
            atomic_writes=True,
            private=True,
        )

    async def async_initialize(self) -> None:
        """Initialize the Spook key/value store."""
        data = await self._persistent_storage.async_load()
        self._store = data or {}

    @callback
    def async_retrieve(self, key: str) -> SpookKeyValueStoreItem:
        """Get a value from the store."""
        # If item is not found, raise an exception
        # Also, if an item is found but is expired (last_modified + ttl is passed now), raise an exception
        if (
            not (item := self._store.get(key))
            and item["ttl"] is not None
            and item["last_modified"] + timedelta(seconds=item["ttl"])
            < datetime.now(tz=UTC)
        ):
            msg = f"Key {key} not found in Spook's key/value store"
            raise KeyError(msg)
        return item

    @callback
    def _persistent_items(self) -> dict[str, SpookKeyValueStoreItem]:
        """Get all persistent items from the store."""
        return {key: item for key, item in self._store.items() if item["persistent"]}

    @callback
    def async_store(
        self,
        key: str,
        value: Any,
        is_persistent: bool | None = None,
        ttl: int | None = _SENTINEL,
    ) -> None:
        """Set a value in the store."""
        if item := self._store.get(key):
            if is_persistent is not None:
                item["is_persistent"] = is_persistent
            if ttl is not _SENTINEL:
                item["ttl"] = ttl
            item["value"] = value
            item["last_modified"] = datetime.now(tz=UTC)
        else:
            item = SpookKeyValueStoreItem(
                key=key,
                value=value,
                is_persistent=is_persistent or True,
                ttl=None if _SENTINEL else ttl,
                last_modified=datetime.now(tz=UTC),
            )
        self._store[key] = item
        self._persistent_storage.async_delay_save(self._persistent_items, 30)

    @callback
    def async_flush(self) -> None:
        """Flush the store."""
        self._store = {}
        self._persistent_storage.async_delay_save(self._persistent_items, 30)

    @callback
    def async_delete(self, key: str) -> None:
        """Delete a value from the store."""
        if key in self._store:
            del self._store[key]
            self._persistent_storage.async_delay_save(self._store, 30)

    @callback
    def async_dump(self) -> dict[str, SpookKeyValueStoreItem]:
        """Dump the store."""
        return self._store

    @callback
    def async_keys(self) -> list[str]:
        """Get all keys in the store."""
        return list(self._store)
