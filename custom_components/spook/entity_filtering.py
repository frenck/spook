"""Spook - Your homie. Entity, registry, and template filtering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    CONF_CHOOSE,
    CONF_DEFAULT,
    CONF_ELSE,
    CONF_ENABLED,
    CONF_PARALLEL,
    CONF_REPEAT,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_THEN,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_START,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import (
    callback,
    valid_entity_id,
)
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.util.hass_dict import HassKey

from .const import LOGGER
from .listeners import async_listen_once_tracked

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from homeassistant.core import HomeAssistant


# Entity domains to ignore when filtering unknown entities
IGNORED_ENTITY_DOMAINS = (
    "device_tracker.",
    "group.",
    "persistent_notification.",
    "scene.",
)

# Home Assistant's legacy time_date platform can create these entity IDs without
# entity-registry entries. Treat them as known so references to configured
# time/date sensors are not reported as unknown when they are not in the state
# machine during an inspection.
KNOWN_TIME_DATE_ENTITY_IDS = {
    "sensor.time",
    "sensor.date",
    "sensor.date_time",
    "sensor.date_time_utc",
    "sensor.date_time_iso",
    "sensor.time_date",
    "sensor.time_utc",
}

# Additional known domains that are not in the Platform enum

# Build a list of all known domains

# Home Assistant core entity ID validation patterns (from homeassistant/core.py)
# Modified _DOMAIN pattern to only match known domains

# Template function names that accept entity IDs as first parameter

# Build regex patterns using Home Assistant's core validation patterns


@dataclass
class EntityIDsCache:
    """Per Home Assistant instance cache of all known entity IDs."""

    entity_ids: set[str] | None = None
    unsubscribe: Callable[[], None] | None = None


DATA_ALL_ENTITY_IDS_CACHE: HassKey[EntityIDsCache] = HassKey(
    "spook_all_entity_ids_cache",
)


@callback
def _async_get_cache(hass: HomeAssistant) -> EntityIDsCache:
    """Return the entity IDs cache container for this instance."""
    if DATA_ALL_ENTITY_IDS_CACHE not in hass.data:
        hass.data[DATA_ALL_ENTITY_IDS_CACHE] = EntityIDsCache()
    return hass.data[DATA_ALL_ENTITY_IDS_CACHE]


def async_setup_all_entity_ids_cache_invalidation(
    hass: HomeAssistant,
) -> Callable[[], None]:
    """Set up event listeners to invalidate the all_entity_ids cache.

    Returns a callable to unsubscribe the listeners.
    """
    cache = _async_get_cache(hass)

    if cache.unsubscribe is not None:
        LOGGER.debug(
            "Spook's entity ID cache invalidation already set up. Skipping.",
        )
        return cache.unsubscribe

    LOGGER.debug("Setting up Spook's all_entity_ids cache invalidation listeners.")

    @callback
    def _clear_cache(*_args: Any) -> None:
        """Clear the cached set of all entity IDs."""
        LOGGER.debug("Clearing all_entity_ids cache.")
        cache.entity_ids = None

    @callback
    def _state_entity_changed(event_data: Mapping[str, Any]) -> bool:
        """Return if a state was added or removed."""
        return (
            event_data.get("old_state") is None or event_data.get("new_state") is None
        )

    # Listen for entity registry updates
    unsub_registry_update = hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED, _clear_cache
    )
    # Listen for Home Assistant start to ensure cache is clear then
    unsub_hass_start = async_listen_once_tracked(
        hass, EVENT_HOMEASSISTANT_START, _clear_cache
    )
    # Listen for components loading
    unsub_component_loaded = hass.bus.async_listen(EVENT_COMPONENT_LOADED, _clear_cache)
    # Listen for state-only entities being added or removed.
    unsub_state_changed = hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        _clear_cache,
        event_filter=_state_entity_changed,
    )

    # Perform an initial clear, just in case.
    _clear_cache()

    def _unsubscribe_listeners() -> None:
        LOGGER.debug(
            "Unsubscribing from Spook's all_entity_ids cache invalidation listeners.",
        )
        unsub_registry_update()
        unsub_hass_start()
        unsub_component_loaded()
        unsub_state_changed()
        cache.entity_ids = None
        cache.unsubscribe = None  # Mark as unsubscribed

    cache.unsubscribe = _unsubscribe_listeners
    return _unsubscribe_listeners


@callback
def async_get_all_entity_ids(
    hass: HomeAssistant, *, include_all_none: bool = False
) -> set[str]:
    """Return entity IDs known to Home Assistant or treated as known by Spook."""
    cache = _async_get_cache(hass)

    if (entity_ids := cache.entity_ids) is None:
        LOGGER.debug(
            "Spook's all_entity_ids cache is empty, populating...",
        )
        entity_registry = er.async_get(hass)
        entity_ids_from_registry = {
            entity.entity_id for entity in entity_registry.entities.values()
        }
        entity_ids_from_states = hass.states.async_entity_ids()

        combined_entity_ids = entity_ids_from_registry.union(
            entity_ids_from_states,
            KNOWN_TIME_DATE_ENTITY_IDS,
        )

        # Filter out ignored domains
        entity_ids = {
            entity_id
            for entity_id in combined_entity_ids
            if not entity_id.startswith(IGNORED_ENTITY_DOMAINS)
        }
        cache.entity_ids = entity_ids
        LOGGER.debug(
            "Spook's all_entity_ids cache populated with %s entities",
            len(entity_ids),
        )

    # Return a copy from the cache, optionally adding ALL/NONE
    if include_all_none:
        return entity_ids.union({ENTITY_MATCH_ALL, ENTITY_MATCH_NONE})
    return entity_ids.copy()


@callback
def async_get_all_area_ids(hass: HomeAssistant) -> set[str]:
    """Return all area IDs, known to Home Assistant."""
    area_registry = ar.async_get(hass)
    return set(area_registry.areas)


@callback
def async_filter_known_area_ids(
    hass: HomeAssistant, *, area_ids: set[str], known_area_ids: set[str] | None = None
) -> set[str]:
    """Filter out known area IDs."""
    if known_area_ids is None:
        known_area_ids = async_get_all_area_ids(hass)
    return {
        area_id for area_id in area_ids - known_area_ids if isinstance(area_id, str)
    }


@callback
def async_get_all_device_ids(hass: HomeAssistant) -> set[str]:
    """Return all device IDs, known to Home Assistant."""
    device_registry = dr.async_get(hass)
    return {device.id for device in device_registry.devices.values()}


@callback
def async_filter_known_device_ids(
    hass: HomeAssistant,
    *,
    device_ids: set[str],
    known_device_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known device IDs."""
    if known_device_ids is None:
        known_device_ids = async_get_all_device_ids(hass)
    return {
        device_id
        for device_id in device_ids - known_device_ids
        if device_id and isinstance(device_id, str)
    }


@callback
def async_filter_known_entity_ids(
    hass: HomeAssistant,
    entity_ids: Iterable[str],
    known_entity_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known entity IDs.

    This callback version skips template processing. For template support,
    use async_filter_known_entity_ids_with_templates instead.
    """
    if known_entity_ids is None:
        known_entity_ids = async_get_all_entity_ids(hass)

    result = set()
    for entity_id_raw in entity_ids:
        if not isinstance(entity_id_raw, str):
            continue

        # Process any comma-separated entity lists
        for entity_id in split_comma_separated_entity_ids(entity_id_raw):
            if (
                not entity_id.startswith(IGNORED_ENTITY_DOMAINS)
                and entity_id not in known_entity_ids
                and valid_entity_id(entity_id)
            ):
                result.add(entity_id)

    return result


@callback
def async_get_all_floor_ids(hass: HomeAssistant) -> set[str]:
    """Return all floor IDs, known to Home Assistant."""
    floor_registry = fr.async_get(hass)
    return {floor.floor_id for floor in floor_registry.floors.values()}


@callback
def async_filter_known_floor_ids(
    hass: HomeAssistant,
    *,
    floor_ids: set[str],
    known_floor_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known floor IDs."""
    if known_floor_ids is None:
        known_floor_ids = async_get_all_floor_ids(hass)
    return {
        floor_id
        for floor_id in floor_ids - known_floor_ids
        if floor_id and isinstance(floor_id, str)
    }


@callback
def async_get_all_label_ids(hass: HomeAssistant) -> set[str]:
    """Return all label IDs, known to Home Assistant."""
    label_registry = lr.async_get(hass)
    return {label.label_id for label in label_registry.labels.values()}


@callback
def async_filter_known_label_ids(
    hass: HomeAssistant,
    *,
    label_ids: set[str],
    known_label_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known label IDs."""
    if known_label_ids is None:
        known_label_ids = async_get_all_label_ids(hass)
    return {
        label_id
        for label_id in label_ids - known_label_ids
        if label_id and isinstance(label_id, str)
    }


@callback
def async_get_all_services(hass: HomeAssistant) -> set[str]:
    """Return all services, known to Home Assistant."""
    return {
        f"{domain}.{service}"
        for domain, services in hass.services.async_services().items()
        for service in services
    }


@callback
def async_filter_known_services(
    hass: HomeAssistant, *, services: set[str], known_services: set[str] | None = None
) -> set[str]:
    """Filter out known services."""
    if known_services is None:
        known_services = async_get_all_services(hass)
    return {
        service.lower()
        for service in services - known_services
        if isinstance(service, str) and service
    }


def split_comma_separated_entity_ids(entity_id: str) -> list[str]:
    """Split comma-separated entity IDs into a list of individual entity IDs.

    Handles both comma-separated entity IDs like "light.living_room,light.kitchen"
    and single entity IDs. Returns a list containing all individual entity IDs.
    """
    if not entity_id or not isinstance(entity_id, str):
        return []

    # Check if the string contains commas
    if "," in entity_id:
        # Split by comma and strip whitespace
        items = [item.strip() for item in entity_id.split(",") if item.strip()]
        if len(items) > 1:
            LOGGER.debug(
                "Split comma-separated entity IDs: %s into %s", entity_id, items
            )
        return items

    # Return the original entity ID in a list if it's not comma-separated
    return [entity_id]


@callback
def async_find_services_in_sequence(  # noqa: C901
    sequence: Sequence[dict[str, Any]],
) -> set[str]:
    """Find all services called in a sequence."""
    called_services: set[str] = set()
    for step in sequence:
        if step.get(CONF_ENABLED) is False:
            continue

        action = cv.determine_script_action(step)

        if action == cv.SCRIPT_ACTION_CALL_SERVICE and CONF_SERVICE in step:
            called_services.add(step[CONF_SERVICE])

        if action == cv.SCRIPT_ACTION_CALL_SERVICE and "action" in step:
            called_services.add(step["action"])

        if action == cv.SCRIPT_ACTION_CHOOSE:
            for choice in step[CONF_CHOOSE]:
                called_services |= async_find_services_in_sequence(
                    choice[CONF_SEQUENCE]
                )
            if nested_sequence := step.get(CONF_DEFAULT):
                called_services |= async_find_services_in_sequence(nested_sequence)

        if action == cv.SCRIPT_ACTION_IF:
            called_services |= async_find_services_in_sequence(step[CONF_THEN])
            if nested_sequence := step.get(CONF_ELSE):
                called_services |= async_find_services_in_sequence(nested_sequence)

        if action == cv.SCRIPT_ACTION_PARALLEL:
            for nested_sequence in step[CONF_PARALLEL]:
                called_services |= async_find_services_in_sequence(
                    nested_sequence[CONF_SEQUENCE]
                )

        if action == cv.SCRIPT_ACTION_REPEAT:
            called_services |= async_find_services_in_sequence(
                step[CONF_REPEAT][CONF_SEQUENCE]
            )

    return called_services
