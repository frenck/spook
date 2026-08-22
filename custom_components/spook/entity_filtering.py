"""Spook - Your homie. Entity, registry, and template filtering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components import automation, script
from homeassistant.const import (
    CONF_CHOOSE,
    CONF_DEFAULT,
    CONF_ELSE,
    CONF_ENABLED,
    CONF_PARALLEL,
    CONF_REPEAT,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
    CONF_SERVICE_DATA_TEMPLATE,
    CONF_THEN,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_START,
    EVENT_STATE_CHANGED,
    Platform,
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
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.util.hass_dict import HassKey

from .const import LOGGER
from .listeners import async_listen_once_tracked

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from homeassistant.core import HomeAssistant


# Entity domains to ignore when filtering unknown entities. These can be
# created on the fly by an action, so a reference to one that does not exist
# yet is not necessarily broken.
#
# Scenes used to be in here for the same reason. They are not any more: a
# scene created by an action is found by scanning for `scene.create` instead,
# which reports the genuinely missing ones rather than none of them. The same
# treatment is possible for `group.set` and `device_tracker.see`.
IGNORED_ENTITY_DOMAINS = (
    "device_tracker.",
    "group.",
    "persistent_notification.",
)

# `scene.create` builds a scene at runtime, named after its `scene_id`.
_SCENE_CREATE_ACTIONS = ("scene.create",)
_CONF_SCENE_ID = "scene_id"

# Placeholders Home Assistant keeps for configurations it could not validate.
_UNAVAILABLE_ENTITY_CLASSES = (
    automation.UnavailableAutomationEntity,
    script.UnavailableScriptEntity,
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


@dataclass
class EntityIDsCache:
    """Per Home Assistant instance cache of all known entity IDs."""

    entity_ids: set[str] | None = None
    entity_ids_by_domain: dict[str, list[str]] | None = None
    created_scene_ids: set[str] | None = None
    rename_suggestions: dict[str, str | None] | None = None
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
        cache.entity_ids_by_domain = None
        cache.created_scene_ids = None
        cache.rename_suggestions = None

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
        cache.entity_ids_by_domain = None
        cache.created_scene_ids = None
        cache.rename_suggestions = None
        cache.unsubscribe = None  # Mark as unsubscribed

    cache.unsubscribe = _unsubscribe_listeners
    return _unsubscribe_listeners


def _find_created_scene_ids(config: Any) -> set[str]:
    """Find scene IDs a configuration creates, at any nesting depth.

    Walks arbitrary nesting rather than the script grammar, because a
    ``scene.create`` step is recognizable on its own and can sit inside any
    branch, repeat or parallel block.
    """
    scene_ids: set[str] = set()

    if isinstance(config, list):
        for item in config:
            scene_ids |= _find_created_scene_ids(item)
        return scene_ids

    if not isinstance(config, dict):
        return scene_ids

    if config.get(CONF_ENABLED) is False:
        return scene_ids

    if config.get("action", config.get(CONF_SERVICE)) in _SCENE_CREATE_ACTIONS:
        # This walks raw configuration, where the legacy `data_template` key
        # has not been folded into `data` yet. Home Assistant accepts both and
        # merges them, so read both rather than preferring one.
        data = {
            key: value
            for payload in (
                config.get(CONF_SERVICE_DATA),
                config.get(CONF_SERVICE_DATA_TEMPLATE),
            )
            if isinstance(payload, dict)
            for key, value in payload.items()
        }
        if data:
            scene_id = data.get(_CONF_SCENE_ID)
            # A templated scene_id cannot be resolved, so it is left alone and
            # the scene it builds stays reportable.
            if isinstance(scene_id, str) and scene_id:
                scene_ids.add(f"{Platform.SCENE}.{scene_id}")

    for value in config.values():
        if isinstance(value, (dict, list)):
            scene_ids |= _find_created_scene_ids(value)

    return scene_ids


@callback
def async_get_created_scene_ids(hass: HomeAssistant) -> set[str]:
    """Return scene entity IDs that configured actions create at runtime.

    ``scene.create`` builds a scene while an automation or script runs, so
    nothing in the registry knows about it until then, and after a restart it
    is gone again until the action runs once more. Referencing one is not a
    broken reference, so collect them and treat them as known.
    """
    cache = _async_get_cache(hass)

    if (scene_ids := cache.created_scene_ids) is None:
        scene_ids = set()
        instances = hass.data.get(DATA_INSTANCES, {})
        for domain in (automation.DOMAIN, script.DOMAIN):
            if (entity_component := instances.get(domain)) is None:
                continue
            for entity in entity_component.entities:
                if isinstance(entity, _UNAVAILABLE_ENTITY_CLASSES):
                    # Kept around for a configuration Home Assistant rejected.
                    # It cannot run, so it creates nothing.
                    continue

                if (raw_config := getattr(entity, "raw_config", None)) is not None:
                    scene_ids |= _find_created_scene_ids(raw_config)
        cache.created_scene_ids = scene_ids
        LOGGER.debug(
            "Spook found %s scenes created by configured actions", len(scene_ids)
        )

    return scene_ids.copy()


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
            async_get_created_scene_ids(hass),
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
def async_get_all_entity_ids_by_domain(hass: HomeAssistant) -> dict[str, list[str]]:
    """Return the known entity IDs, grouped by domain.

    Looking for a similarly named entity only makes sense within a domain, and
    comparing against every entity in the instance is the expensive way to
    find that out.
    """
    cache = _async_get_cache(hass)

    if (by_domain := cache.entity_ids_by_domain) is None:
        by_domain = {}
        for entity_id in async_get_all_entity_ids(hass):
            by_domain.setdefault(entity_id.split(".", 1)[0], []).append(entity_id)
        cache.entity_ids_by_domain = by_domain

    return by_domain


@callback
def async_get_rename_suggestion_cache(hass: HomeAssistant) -> dict[str, str | None]:
    """Return the per-instance cache of rename suggestions.

    One missing entity is usually referenced from several automations, and each
    of those builds its own issue description. Without this, the same string
    comparison runs once per reference instead of once per entity.
    """
    cache = _async_get_cache(hass)

    if cache.rename_suggestions is None:
        cache.rename_suggestions = {}

    return cache.rename_suggestions


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
    device_ids = {device.id for device in device_registry.devices.values()}

    # Home Assistant Core 2026.8 split devices that belonged to multiple config
    # entries into one device per config entry. The pre-split device ID is no
    # longer registered, but it still resolves to those new devices, so anything
    # targeting it keeps working. Those IDs are known, just not enumerated.
    # Can be removed when Core drops composite devices in 2027.8.
    get_composite_splits: Callable[[], Mapping[str, Any]] | None = getattr(
        device_registry.devices, "get_composite_splits", None
    )
    if get_composite_splits is not None:
        device_ids.update(get_composite_splits().keys())

    return device_ids


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
def async_drop_existing_action_names(
    hass: HomeAssistant,
    candidates: set[str],
) -> set[str]:
    """Return the candidates with existing action names removed.

    An action name has the same shape as an entity ID, and some of them reach
    a reference check as if they were one. A legacy notify group is the common
    case: `notify.my_phone` is an action and no entity at all, and Home
    Assistant reports it as a referenced entity when an automation uses it as
    a legacy target. Scanning action payloads turns up the same thing, in
    third-party actions that take a list of notifier names.

    Nothing is dangling in either case, so an existing action is not an
    unknown entity. Reporting it sends people looking for an entity that was
    never supposed to exist.

    Asks the registry per candidate rather than building the set of every
    action in the instance, because this runs once per inspected item while
    the candidates are only ever the handful that looked broken.
    """
    if not candidates:
        return candidates

    return {
        candidate
        for candidate in candidates
        # Guarded: an exception here would abort the whole inspection, and not
        # every caller has already checked the shape.
        if "." not in candidate
        or not hass.services.has_service(*candidate.split(".", 1))
    }


@callback
def async_filter_known_entity_ids(
    hass: HomeAssistant,
    entity_ids: Iterable[str],
    known_entity_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known entity IDs, and names that are actions.

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

    return async_drop_existing_action_names(hass, result)


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


def _find_services_in_call_service_step(step: dict[str, Any]) -> set[str]:
    """Find the service called by a `service`/`action` step."""
    called_services: set[str] = set()
    if CONF_SERVICE in step:
        called_services.add(step[CONF_SERVICE])
    if "action" in step:
        called_services.add(step["action"])
    return called_services


def _find_services_in_choose_step(step: dict[str, Any]) -> set[str]:
    """Find the services called by a `choose` step's branches."""
    called_services: set[str] = set()
    for choice in step[CONF_CHOOSE]:
        called_services |= async_find_services_in_sequence(choice[CONF_SEQUENCE])
    if nested_sequence := step.get(CONF_DEFAULT):
        called_services |= async_find_services_in_sequence(nested_sequence)
    return called_services


def _find_services_in_if_step(step: dict[str, Any]) -> set[str]:
    """Find the services called by an `if` step's branches."""
    called_services = async_find_services_in_sequence(step[CONF_THEN])
    if nested_sequence := step.get(CONF_ELSE):
        called_services |= async_find_services_in_sequence(nested_sequence)
    return called_services


def _find_services_in_parallel_step(step: dict[str, Any]) -> set[str]:
    """Find the services called by a `parallel` step's sequences."""
    called_services: set[str] = set()
    for nested_sequence in step[CONF_PARALLEL]:
        called_services |= async_find_services_in_sequence(
            nested_sequence[CONF_SEQUENCE]
        )
    return called_services


def _find_services_in_repeat_step(step: dict[str, Any]) -> set[str]:
    """Find the services called by a `repeat` step's sequence."""
    return async_find_services_in_sequence(step[CONF_REPEAT][CONF_SEQUENCE])


_STEP_FINDERS: dict[str, Callable[[dict[str, Any]], set[str]]] = {
    cv.SCRIPT_ACTION_CALL_SERVICE: _find_services_in_call_service_step,
    cv.SCRIPT_ACTION_CHOOSE: _find_services_in_choose_step,
    cv.SCRIPT_ACTION_IF: _find_services_in_if_step,
    cv.SCRIPT_ACTION_PARALLEL: _find_services_in_parallel_step,
    cv.SCRIPT_ACTION_REPEAT: _find_services_in_repeat_step,
}


def _async_find_services_in_step(action: str, step: dict[str, Any]) -> set[str]:
    """Find the services called or nested within a single script step."""
    finder = _STEP_FINDERS.get(action)
    return finder(step) if finder is not None else set()


@callback
def async_find_services_in_sequence(
    sequence: Sequence[dict[str, Any]],
) -> set[str]:
    """Find all services called in a sequence."""
    called_services: set[str] = set()
    for step in sequence:
        if step.get(CONF_ENABLED) is False:
            continue

        action = cv.determine_script_action(step)

        if action == cv.SCRIPT_ACTION_CHECK_CONDITION:
            # A bare condition stops the sequence at runtime when false, so
            # later steps are only conditionally reached. Stop scanning them to
            # avoid reporting actions of integrations that are gated off on
            # purpose, e.g. multi-integration blueprints.
            break

        called_services |= _async_find_services_in_step(action, step)

    return called_services
