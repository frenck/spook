"""Spook - Your homie. Checking a draft for ghosts before it is saved.

Every unknown-reference repair waits for something to be saved, loaded and
then broken. This asks them the same question about something that is not
saved yet: the repairs themselves look at the draft, with the same readers
and the same idea of what exists. A second copy of that logic here would
drift from the repairs, and then a draft that passed would still get a repair
the moment it was saved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import probatio

from homeassistant.components import automation, script
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script

from .dashboard_extraction import (
    extract_actions_from_dashboard_node,
    extract_areas_from_dashboard_node,
    extract_entities_from_dashboard_node,
)
from .ectoplasms.automation.repairs import (
    unknown_area_references as automation_areas,
    unknown_condition_references as automation_conditions,
    unknown_device_references as automation_devices,
    unknown_entity_references as automation_entities,
    unknown_floor_references as automation_floors,
    unknown_label_references as automation_labels,
    unknown_service_references as automation_services,
    unknown_trigger_references as automation_triggers,
)
from .ectoplasms.script.repairs import (
    unknown_area_references as script_areas,
    unknown_condition_references as script_conditions,
    unknown_device_references as script_devices,
    unknown_entity_references as script_entities,
    unknown_floor_references as script_floors,
    unknown_label_references as script_labels,
    unknown_service_references as script_services,
    unknown_trigger_references as script_triggers,
)
from .entity_filtering import (
    async_filter_known_area_ids,
    async_filter_known_entity_ids,
    async_filter_known_services,
    async_get_all_entity_ids,
    async_get_deleted_entities,
    async_get_rename_suggestion_cache,
)
from .entity_suggestions import async_warm_rename_suggestions

if TYPE_CHECKING:
    from types import ModuleType

    from homeassistant.core import HomeAssistant

    from .repairs import AbstractSpookEntityComponentUnknownReferencesRepair

type DraftKind = Literal["automation", "script", "scene", "dashboard"]

DRAFT_KINDS: tuple[DraftKind, ...] = ("automation", "script", "scene", "dashboard")

# The repairs that read an automation or a script, and nothing else. Listed
# rather than discovered: a new repair that cannot take a draft would
# otherwise be handed one, and find out in front of somebody. A test holds
# this list to the repairs on disk, so a new one cannot be forgotten here.
DRAFT_REPAIRS: dict[str, tuple[ModuleType, ...]] = {
    automation.DOMAIN: (
        automation_areas,
        automation_conditions,
        automation_devices,
        automation_entities,
        automation_floors,
        automation_labels,
        automation_services,
        automation_triggers,
    ),
    script.DOMAIN: (
        script_areas,
        script_conditions,
        script_devices,
        script_entities,
        script_floors,
        script_labels,
        script_services,
        script_triggers,
    ),
}


class DraftError(Exception):
    """A draft that cannot be read as what it says it is."""


class _DraftEntity:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """What the repairs read off an automation or script, made from a draft.

    The repairs take an entity, because that is what they find in a running
    house. A draft has none, so this stands in for it with the parts they
    read: the configuration as written, and Home Assistant's own script for
    what Home Assistant itself would say the steps reference.
    """

    def __init__(
        self, hass: HomeAssistant, domain: str, config: dict[str, Any]
    ) -> None:
        """Build the stand-in, validating the steps the way Home Assistant does."""
        steps_key = "sequence" if domain == script.DOMAIN else "actions"
        steps = config.get(steps_key, config.get("action", []))

        try:
            sequence = cv.SCRIPT_SCHEMA(steps)
        except probatio.Invalid as err:
            message = f"The steps of this {domain} do not validate: {err}"
            raise DraftError(message) from err

        # Not a top-level script, so Home Assistant does not count it among
        # the scripts to stop at shutdown. It never runs anyway.
        loaded = Script(hass, sequence, "draft", domain, top_level=False)

        self.raw_config = config
        self.entity_id = f"{domain}.draft"
        self.name = config.get("alias", "draft")
        self.unique_id = None
        self.is_on = True

        # Automations and scripts keep their script under different names.
        self.action_script = loaded
        self.script = loaded

        self.referenced_areas = loaded.referenced_areas
        self.referenced_devices = loaded.referenced_devices
        self.referenced_entities = loaded.referenced_entities
        self.referenced_floors = loaded.referenced_floors
        self.referenced_labels = loaded.referenced_labels


async def _async_check_with_repairs(
    hass: HomeAssistant, domain: str, config: dict[str, Any]
) -> dict[str, list[str]]:
    """Return what the repairs for this domain find unknown in the draft."""
    draft = _DraftEntity(hass, domain, config)
    unknown: dict[str, list[str]] = {}

    for module in DRAFT_REPAIRS[domain]:
        repair: AbstractSpookEntityComponentUnknownReferencesRepair = (
            module.SpookRepair(hass)
        )
        # The two hooks a repair runs on every entity in a round, in the
        # order it runs them. Protected, as they are not meant to be called
        # from outside a round; this is the one round that has no house.
        # pylint: disable-next=protected-access
        await repair._async_setup_inspection()  # noqa: SLF001
        # pylint: disable-next=protected-access
        found = await repair._async_compute_unknown_references(draft)  # noqa: SLF001
        if found:
            unknown[repair.reference_label] = sorted(found)

    return unknown


def _check_scene(hass: HomeAssistant, config: dict[str, Any]) -> dict[str, list[str]]:
    """Return the entities a draft scene sets that do not exist.

    Asked the way the scene repair asks it, of the entities it sets.
    """
    entities = config.get("entities")
    if not isinstance(entities, dict):
        message = "A scene sets its entities under `entities`, as a mapping"
        raise DraftError(message)

    unknown = async_filter_known_entity_ids(
        hass, entity_ids=set(entities), known_entity_ids=async_get_all_entity_ids(hass)
    )
    return {"entities": sorted(unknown)} if unknown else {}


def _check_dashboard(
    hass: HomeAssistant, config: dict[str, Any]
) -> dict[str, list[str]]:
    """Return what a draft card, view or dashboard names that does not exist.

    The dashboard readers take any node, so a single card is as welcome as a
    whole dashboard. Filtered the way the dashboard repairs filter.
    """
    checks = {
        "entities": async_filter_known_entity_ids(
            hass,
            entity_ids=extract_entities_from_dashboard_node(config),
            known_entity_ids=async_get_all_entity_ids(hass, include_all_none=True),
        ),
        "areas": async_filter_known_area_ids(
            hass, area_ids=extract_areas_from_dashboard_node(config)
        ),
        "services": async_filter_known_services(
            hass, services=extract_actions_from_dashboard_node(config)
        ),
    }
    return {label: sorted(found) for label, found in checks.items() if found}


async def async_describe_unknown_entities(
    hass: HomeAssistant, entity_ids: list[str]
) -> list[dict[str, str]]:
    """Return the unknown entities with what Spook can say about each.

    The same caches the repairs describe them from: when one was deleted and
    by what, or the entity it was most likely renamed to.
    """
    await async_warm_rename_suggestions(hass, entity_ids)
    deleted_by_entity_id = async_get_deleted_entities(hass)
    suggestions = async_get_rename_suggestion_cache(hass)

    described: list[dict[str, str]] = []
    for entity_id in entity_ids:
        detail = {"entity_id": entity_id}
        if (deleted := deleted_by_entity_id.get(entity_id)) is not None:
            detail["deleted_on"] = deleted.modified_at.date().isoformat()
            detail["was_provided_by"] = deleted.platform
        elif suggestion := suggestions.get(entity_id):
            detail["did_you_mean"] = suggestion
        described.append(detail)

    return described


async def async_check_draft(
    hass: HomeAssistant, kind: DraftKind, config: dict[str, Any]
) -> dict[str, list[str]]:
    """Return what in the draft does not exist, by type. Empty means clean.

    Raises `DraftError` when the draft cannot be read as that kind.
    """
    if kind == "scene":
        return _check_scene(hass, config)
    if kind == "dashboard":
        return _check_dashboard(hass, config)
    return await _async_check_with_repairs(hass, kind, config)
