"""Spook - Your homie. Finding where something is used.

The other side of what the unknown-reference repairs do. They read every
automation, script, scene and dashboard and ask what in there is missing;
this reads the same things, the same way, and asks where one thing turns up.
Same readers on purpose: an answer that disagreed with a repair about what an
automation names would be worse than no answer.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from homeassistant.components import automation, lovelace, script
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES

from .action_extraction import async_extract_entities_from_action_config
from .dashboard_extraction import (
    extract_actions_from_dashboard_node,
    extract_areas_from_dashboard_node,
    extract_entities_from_dashboard_node,
)
from .ectoplasms.automation.repairs.unknown_entity_references import (
    extract_entities_from_automation_config,
)
from .ectoplasms.lovelace.dashboards import async_dashboard_configs
from .ectoplasms.script.repairs.unknown_entity_references import (
    extract_referenced_entities_from_script,
)
from .entity_filtering import (
    async_find_services_in_sequence,
    async_get_all_services,
    async_name_helper_in_the_registry,
)
from .helper_sources import SOURCE_OPTION_KEYS, async_helper_sources
from .reference_extraction import extract_targets_from_config
from .repairs import INSPECTION_YIELD_INTERVAL
from .template_extraction import async_extract_entities_from_config

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

type ReferenceType = Literal["entity", "action", "area", "floor", "label"]

REFERENCE_TYPES: tuple[ReferenceType, ...] = (
    "entity",
    "action",
    "area",
    "floor",
    "label",
)

# A template helper keeps its templates in its options, which is exactly the
# kind of configuration the template reader walks.
_TEMPLATE_HELPER_DOMAIN = "template"

# Where Home Assistant keeps the scenes made in the UI and in YAML.
_SCENES = "homeassistant_scene"


@dataclass(frozen=True, slots=True)
class Usage:
    """One place something is used in."""

    kind: str
    id: str
    name: str
    matched_as: ReferenceType
    edit_url: str | None = None

    def as_dict(self) -> dict[str, str]:
        """Return the usage the way a tool hands it over."""
        usage = {
            "kind": self.kind,
            "id": self.id,
            "name": self.name,
            "matched_as": self.matched_as,
        }
        if self.edit_url is not None:
            usage["edit_url"] = self.edit_url
        return usage


def reference_types_for(reference: str) -> tuple[ReferenceType, ...]:
    """Return what a reference could be, judged by its shape alone.

    Something with a dot in it is an entity or an action, and `script.wake_up`
    is honestly both. Without one it is the ID of an area, a floor or a label,
    and those share a namespace of slugs, so all three are worth a look.
    """
    if "." in reference:
        return ("entity", "action")
    return ("area", "floor", "label")


def _edit_url(domain: str, entity: Any) -> str:
    """Return where to edit an automation, script or scene.

    Without a unique ID it was written in YAML and has no editor of its own,
    the same fallback the repairs use.
    """
    if entity.unique_id is None:
        return f"/config/{domain}/dashboard"
    return f"/config/{domain}/edit/{entity.unique_id}"


async def _async_named_by_automation(
    hass: HomeAssistant,
    entity: Any,
    wanted: tuple[ReferenceType, ...],
    known_services: set[str],
) -> dict[ReferenceType, set[str]]:
    """Return what one automation names, read the way its repairs read it."""
    raw_config = getattr(entity, "raw_config", None) or {}
    named: dict[ReferenceType, set[str]] = {}

    if "entity" in wanted:
        named["entity"] = (
            set(entity.referenced_entities)
            | await extract_entities_from_automation_config(
                hass, raw_config, known_services
            )
            | await async_extract_entities_from_config(hass, raw_config, known_services)
        )

    # One that failed to load has no script to read the actions off.
    if "action" in wanted and (action_script := getattr(entity, "action_script", None)):
        named["action"] = async_find_services_in_sequence(action_script.sequence)

    _add_targets(named, entity, raw_config, wanted)
    return named


async def _async_named_by_script(
    hass: HomeAssistant,
    entity: Any,
    wanted: tuple[ReferenceType, ...],
    known_services: set[str],
) -> dict[ReferenceType, set[str]]:
    """Return what one script names, read the way its repairs read it."""
    raw_config = getattr(entity, "raw_config", None) or {}
    named: dict[ReferenceType, set[str]] = {}
    # Same as above: a script that failed to load has nothing to run.
    loaded = getattr(entity, "script", None)

    if "entity" in wanted:
        steps = raw_config.get("sequence") or []
        named["entity"] = (
            (extract_referenced_entities_from_script(entity) if loaded else set())
            | await async_extract_entities_from_action_config(
                hass,
                [steps] if isinstance(steps, dict) else steps,
                known_services=known_services,
            )
            | await async_extract_entities_from_config(hass, raw_config, known_services)
        )

    if "action" in wanted and loaded:
        named["action"] = async_find_services_in_sequence(loaded.sequence)

    _add_targets(named, loaded or entity, raw_config, wanted)
    return named


def _add_targets(
    named: dict[ReferenceType, set[str]],
    source: Any,
    raw_config: Any,
    wanted: tuple[ReferenceType, ...],
) -> None:
    """Add the areas, floors and labels, from Home Assistant and the raw config.

    Home Assistant's own lists miss what sits in a `repeat`, Spook's walker
    picks that up, and the repairs take both. So does this.
    """
    targets = extract_targets_from_config(raw_config)
    if "area" in wanted:
        named["area"] = set(getattr(source, "referenced_areas", ())) | targets.area_ids
    if "floor" in wanted:
        named["floor"] = (
            set(getattr(source, "referenced_floors", ())) | targets.floor_ids
        )
    if "label" in wanted:
        named["label"] = (
            set(getattr(source, "referenced_labels", ())) | targets.label_ids
        )


def _matches(
    named: dict[ReferenceType, set[str]], reference: str
) -> list[ReferenceType]:
    """Return what the reference was found as, in the order it was asked."""
    return [kind for kind, found in named.items() if reference in found]


async def _async_find_in_automations_and_scripts(
    hass: HomeAssistant,
    reference: str,
    wanted: tuple[ReferenceType, ...],
    known_services: set[str],
) -> list[Usage]:
    """Return the automations and scripts that use the reference."""
    usages: list[Usage] = []
    instances = hass.data.get(DATA_INSTANCES, {})

    for domain, reader in (
        (automation.DOMAIN, _async_named_by_automation),
        (script.DOMAIN, _async_named_by_script),
    ):
        if (component := instances.get(domain)) is None:
            continue

        # A snapshot, like the repairs take: this gives the loop a turn now and
        # then, and an automation added during one changes the collection.
        for index, entity in enumerate(list(component.entities)):
            if index and index % INSPECTION_YIELD_INTERVAL == 0:
                await asyncio.sleep(0)

            named = await reader(hass, entity, wanted, known_services)
            usages.extend(
                Usage(
                    kind=domain,
                    id=entity.entity_id,
                    name=entity.name or entity.entity_id,
                    matched_as=matched_as,
                    edit_url=_edit_url(domain, entity),
                )
                for matched_as in _matches(named, reference)
            )

    return usages


def _find_in_scenes(hass: HomeAssistant, reference: str) -> list[Usage]:
    """Return the scenes that set the entity."""
    if (scenes := hass.data.get(_SCENES)) is None:
        return []

    return [
        Usage(
            kind="scene",
            id=entity.entity_id,
            name=entity.name or entity.entity_id,
            matched_as="entity",
            edit_url=_edit_url("scene", entity),
        )
        for entity in list(scenes.entities.values())
        if reference in entity.scene_config.states
    ]


def _named_by_view(
    view: Any, wanted: tuple[ReferenceType, ...]
) -> dict[ReferenceType, set[str]]:
    """Return what one dashboard view names, read the way its repairs read it."""
    named: dict[ReferenceType, set[str]] = {}
    if "entity" in wanted:
        named["entity"] = extract_entities_from_dashboard_node(view)
    if "action" in wanted:
        named["action"] = extract_actions_from_dashboard_node(view)
    if "area" in wanted:
        named["area"] = extract_areas_from_dashboard_node(view)
    return named


async def _async_find_in_dashboards(
    hass: HomeAssistant, reference: str, wanted: tuple[ReferenceType, ...]
) -> list[Usage]:
    """Return the dashboards that use the reference, pointing at the first view."""
    if (lovelace_data := hass.data.get(lovelace.DOMAIN)) is None:
        return []

    usages: list[Usage] = []
    async for dashboard, url_path, config in async_dashboard_configs(
        lovelace_data.dashboards
    ):
        if not isinstance(config, dict):
            continue

        title = (dashboard.config or {}).get("title", url_path)
        found: dict[ReferenceType, int | str] = {}
        for view_index, view in enumerate(config.get("views") or []):
            if not isinstance(view, dict):
                continue
            for matched_as in _matches(_named_by_view(view, wanted), reference):
                found.setdefault(matched_as, view.get("path") or view_index)

        usages.extend(
            Usage(
                kind="dashboard",
                id=url_path,
                name=title,
                matched_as=matched_as,
                edit_url=f"/{url_path}/{view_path}?edit=1",
            )
            for matched_as, view_path in found.items()
        )

    return usages


async def _async_find_in_helpers(
    hass: HomeAssistant, reference: str, known_services: set[str]
) -> list[Usage]:
    """Return the helpers that take the entity as a source, or in a template.

    A helper can store its source as an entity registry ID rather than an
    entity ID, so each one is resolved before it is compared.
    """
    entity_registry = er.async_get(hass)
    usages: list[Usage] = []

    for entry in hass.config_entries.async_entries():
        if entry.domain in SOURCE_OPTION_KEYS or entry.domain == "bayesian":
            sources = {
                er.async_resolve_entity_id(entity_registry, source) or source
                for source in async_helper_sources(entry)
            }
            kind = "helper"
        elif entry.domain == _TEMPLATE_HELPER_DOMAIN:
            sources = await async_extract_entities_from_config(
                hass, dict(entry.options), known_services
            )
            kind = "template"
        else:
            continue

        if reference in sources:
            usages.append(
                Usage(
                    kind=kind,
                    id=async_name_helper_in_the_registry(hass, entry.entry_id),
                    name=entry.title,
                    matched_as="entity",
                )
            )

    return usages


async def async_find_usages(
    hass: HomeAssistant,
    reference: str,
    reference_types: tuple[ReferenceType, ...],
) -> list[Usage]:
    """Return every place the reference is used, as any of the given types."""
    known_services = async_get_all_services(hass)

    usages = await _async_find_in_automations_and_scripts(
        hass, reference, reference_types, known_services
    )
    usages.extend(await _async_find_in_dashboards(hass, reference, reference_types))

    # Scenes and helpers only ever hold entities.
    if "entity" in reference_types:
        usages.extend(_find_in_scenes(hass, reference))
        usages.extend(await _async_find_in_helpers(hass, reference, known_services))

    return usages
