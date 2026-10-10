"""Running a corpus case through what Spook's repairs read.

Layer one of the corpus: configuration in, references out. Nothing here
reads a configuration itself. Each kind is handed to Home Assistant's own
setup, as written, and then to the very repairs that look at that kind, so
a reader that changes changes what the corpus sees. Home Assistant's YAML
tags arrive as the opaque strings the case loader made of them, never
resolved.

The house is empty: no entities, areas, devices, services or anything else,
apart from Home Assistant's own core integration, which every house has, and
the integration being read. Their own actions therefore exist.
That turns every repair's "what is unknown here" into "everything it would
report if nothing existed", which is every reference it reads, after the
filtering it does to tell a reference from something that only looks like
one. Three types cannot be asked that way, and are taken one step earlier:

- triggers and conditions: Home Assistant's own platforms always exist, so
  the check against them is left out and every key the repair reads counts;
- attributes and states: what an entity has comes from history, which an
  empty house does not have, so these are the pairs the repair would ask the
  recorder about.

The entity repairs report what is no entity ID at all, like
`cover.blind.current_position`, together with the entities that do not
exist, and the issue says them apart. So does the result: those are under
`not_entity_ids`, the rest under `entities`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.components import automation, homeassistant, script
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.setup import async_setup_component

from custom_components.spook.dashboard_extraction import (
    extract_not_entity_ids_from_dashboard_node,
)
from custom_components.spook.draft_checking import DRAFT_REPAIRS
from custom_components.spook.ectoplasms.lovelace.repairs import (
    unknown_area_references as dashboard_areas,
    unknown_entity_references as dashboard_entities,
    unknown_service_references as dashboard_services,
)
from custom_components.spook.entity_filtering import is_not_an_entity_id
from custom_components.spook.repairs import AbstractSpookUnknownEntityNamesRepair

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from types import ModuleType

    from homeassistant.core import HomeAssistant

    from custom_components.spook.repairs import AbstractSpookRepair

# The repairs reading automations and scripts, as Spook lists them for
# checking a draft. A test holds that list to the repairs on disk.
AUTOMATION_REPAIRS = DRAFT_REPAIRS[automation.DOMAIN]
SCRIPT_REPAIRS = DRAFT_REPAIRS[script.DOMAIN]

# The repairs reading dashboards for references. The resource repairs read
# the resource list, not a dashboard, so they are not in here.
DASHBOARD_REPAIRS: dict[str, ModuleType] = {
    "entities": dashboard_entities,
    "areas": dashboard_areas,
    "services": dashboard_services,
}

# Where a repair asks whether an integration can provide a trigger or a
# condition. Left out, see the module docstring.
_PLATFORM_CHECKS = (
    "async_filter_unknown_trigger_keys",
    "async_filter_unknown_condition_keys",
)

# Every view type Home Assistant has. Anything else at the top of a case
# that is not a whole dashboard is a card.
_VIEW_TYPES = frozenset({"masonry", "panel", "sections", "sidebar"})


def _reference_label(module: ModuleType) -> str:
    """Return the reference type a repair module reports."""
    return module.SpookRepair.reference_label


# Where the result lists what is no entity ID, said apart from `entities`.
NOT_ENTITY_IDS = "not_entity_ids"


def reference_types(kind: str) -> frozenset[str]:
    """Return the reference types the harness reports for a kind."""
    if kind == "dashboard":
        labels = set(DASHBOARD_REPAIRS)
    else:
        repairs = AUTOMATION_REPAIRS if kind == "automation" else SCRIPT_REPAIRS
        labels = {_reference_label(module) for module in repairs}

    return frozenset({*labels, NOT_ENTITY_IDS})


def _say_apart(result: dict[str, Any], is_no_entity_id: Callable[[str], bool]) -> None:
    """Move what is no entity ID from `entities` to its own list in a result.

    By the same rule the issue uses to say them apart.
    """
    reported = result["entities"]
    result["entities"] = [value for value in reported if not is_no_entity_id(value)]
    result[NOT_ENTITY_IDS] = [value for value in reported if is_no_entity_id(value)]


async def _async_setup_house(hass: HomeAssistant) -> None:
    """Set up what every house has before anything is read.

    Home Assistant's core integration is always there, so its actions, like
    `homeassistant.turn_on`, exist and check what they are handed.
    """
    assert await async_setup_component(hass, homeassistant.DOMAIN, {})


async def _every_key(_hass: HomeAssistant, keys: Iterable[str]) -> set[str]:
    """Count every trigger or condition key, known platform or not."""
    return set(keys)


async def _async_round_findings(
    repair: AbstractSpookRepair, module: ModuleType
) -> list[str]:
    """Run one round of a repair and return what it would raise an issue for.

    The round itself, so the corpus goes past the same doors: which entities
    are looked at, which are skipped, and what is filtered on the way out.
    """
    found: set[str] = set()

    def _capture(**kwargs: Any) -> None:
        found.update(kwargs["references"])

    platform_checks = {
        name: patch.object(module, name, _every_key)
        for name in _PLATFORM_CHECKS
        if hasattr(module, name)
    }
    with patch.object(repair, "async_create_issue", _capture):
        for check in platform_checks.values():
            check.start()
        try:
            await repair.async_inspect()
        finally:
            for check in platform_checks.values():
                check.stop()

    return sorted(found)


async def async_load_component_entity(
    hass: HomeAssistant, domain: str, config: dict[str, Any]
) -> Any:
    """Load one automation or script through Home Assistant, and return it.

    Through Home Assistant's own setup, so the entity is the one the repairs
    find in a running house: validated, with its own idea of what it
    references, and unavailable when Home Assistant would not load it.
    """
    await _async_setup_house(hass)

    if domain == automation.DOMAIN:
        component_config: Any = [config]
    else:
        component_config = {"corpus": config}

    assert await async_setup_component(hass, domain, {domain: component_config})
    await hass.async_block_till_done()

    entities = list(hass.data[DATA_INSTANCES][domain].entities)
    assert len(entities) == 1, f"Expected one {domain}, Home Assistant made {entities}"
    return entities[0]


async def async_component_references(
    hass: HomeAssistant, domain: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Return what the repairs for automations or scripts read in a config."""
    entity = await async_load_component_entity(hass, domain, config)
    unavailable_class = (
        automation.UnavailableAutomationEntity
        if domain == automation.DOMAIN
        else script.UnavailableScriptEntity
    )

    result: dict[str, Any] = {"loaded": not isinstance(entity, unavailable_class)}
    for module in DRAFT_REPAIRS[domain]:
        repair = module.SpookRepair(hass)
        label = _reference_label(module)

        # These work out a whole round up front, asking the recorder. Their
        # reading is one step before that, and asked of this entity alone.
        if isinstance(repair, AbstractSpookUnknownEntityNamesRepair):
            named: set[tuple[str, str]] = set()
            raw_config = getattr(entity, "raw_config", None)
            # pylint: disable-next=protected-access
            if isinstance(raw_config, dict) and repair._is_inspected(entity):  # noqa: SLF001
                # pylint: disable-next=protected-access
                named = repair._named_in(entity, raw_config)  # noqa: SLF001
            result[label] = sorted(f"{entity_id}: {name}" for entity_id, name in named)
            continue

        result[label] = await _async_round_findings(repair, module)

    _say_apart(result, is_not_an_entity_id)

    # A loaded automation has its triggers attached, and a time trigger
    # leaves a timer behind that fails the test once it is over.
    if domain == automation.DOMAIN and result["loaded"]:
        await hass.services.async_call(
            automation.DOMAIN,
            "turn_off",
            {"entity_id": entity.entity_id},
            blocking=True,
        )

    return result


class _CorpusDashboard:  # pylint: disable=too-few-public-methods
    """What the dashboard repairs read off a dashboard, made from a case.

    The repairs go through Home Assistant's dashboards and load each one.
    This stands in for one of them with the parts they read.
    """

    url_path = "corpus"
    config = None

    def __init__(self, dashboard: dict[str, Any]) -> None:
        """Hold the dashboard configuration this stands in for."""
        self._dashboard = dashboard

    async def async_load(self, *, force: bool) -> dict[str, Any]:
        """Return the dashboard configuration, like a loaded dashboard does."""
        _ = force
        return self._dashboard


def as_dashboard(config: dict[str, Any]) -> dict[str, Any]:
    """Return a case as a whole dashboard, whether it is one, a view or a card.

    The repairs read dashboards, view by view, or the strategy at the root of
    one that has no views stored. A view or a card on its own is put where it
    would sit, so it is read exactly the same way.
    """
    if "views" in config or isinstance(config.get("strategy"), dict):
        return config

    is_view = config.get("type") in _VIEW_TYPES or (
        "type" not in config and {"cards", "sections", "badges"} & config.keys()
    )
    if is_view:
        return {"views": [config]}
    return {"views": [{"cards": [config]}]}


async def async_dashboard_references(
    hass: HomeAssistant, config: dict[str, Any]
) -> dict[str, Any]:
    """Return what the dashboard repairs read in a dashboard, view or card."""
    await _async_setup_house(hass)
    dashboard_config = as_dashboard(config)
    dashboard = _CorpusDashboard(dashboard_config)

    result: dict[str, Any] = {}
    for label, module in DASHBOARD_REPAIRS.items():
        repair = module.SpookRepair(hass)
        # Normally taken from Home Assistant when the repair is activated.
        # pylint: disable-next=protected-access
        repair._dashboards = {dashboard.url_path: dashboard}  # noqa: SLF001
        result[label] = await _async_round_findings(repair, module)

    # The dashboard issue says apart what its own reader finds, not whatever
    # looks like no entity ID, so that reader decides here too.
    not_entity_ids = extract_not_entity_ids_from_dashboard_node(dashboard_config)
    _say_apart(result, lambda value: value in not_entity_ids)

    return result
