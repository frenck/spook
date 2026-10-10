"""Tests for asking Home Assistant what an automation or script references.

Home Assistant builds those lists from the action data too, and action data
is whatever somebody wrote. An `entity_id: 42` in there, or a list holding a
mapping, makes it raise a `TypeError` for that one automation or script. That
used to take the whole round down with it, so every other one went unchecked.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
import importlib
import logging
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.helpers import (
    area_registry as ar,
    floor_registry as fr,
    issue_registry as ir,
    label_registry as lr,
)
from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.draft_checking import async_check_draft
from custom_components.spook.repairs import HelperUnknownSourcesFixFlow
from custom_components.spook.usage_finding import async_find_usages
from tests.repair_helpers import async_issue_about
import pytest

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er

# Comfortably past the grace period the empty area, floor and label repairs
# give something new.
_AGED = timedelta(days=2)

# What each kind is called in a step, and one of it that does not exist.
_KINDS = {
    "entity": ("entity_id", "light.xghost", "light.xphantom"),
    "device": (
        "device_id",
        "0123456789abcdef0123456789abcdef",
        "fedcba9876543210fedcba9876543210",
    ),
    "area": ("area_id", "xghost", "xphantom"),
    "floor": ("floor_id", "xghost", "xphantom"),
    "label": ("label_id", "xghost", "xphantom"),
}

# Both make Home Assistant raise, each with a `TypeError` of its own.
_UNREADABLE = [
    pytest.param(42, id="number"),
    pytest.param([{"name": "kitchen"}], id="list-holding-a-mapping"),
]


def _steps(key: str, unreadable: Any, unknown: str) -> list[dict[str, Any]]:
    """Return steps Home Assistant cannot list, next to an unknown reference."""
    return [
        {"action": "light.turn_on", "data": {key: unreadable}},
        {"action": "light.turn_on", "target": {key: unknown}},
    ]


def _automation(alias: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    """Return an automation running the steps."""
    return {
        "id": alias,
        "alias": alias,
        "triggers": [{"trigger": "event", "event_type": "spook_test"}],
        "actions": steps,
    }


async def _async_set_up(
    hass: HomeAssistant, domain: str, configs: dict[str, list[dict[str, Any]]]
) -> None:
    """Load real automations or scripts, one for each set of steps."""
    if domain == "automation":
        config: Any = [_automation(alias, steps) for alias, steps in configs.items()]
    else:
        config = {alias: {"sequence": steps} for alias, steps in configs.items()}

    assert await async_setup_component(hass, domain, {domain: config})
    await hass.async_block_till_done()


@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize("kind", list(_KINDS))
@pytest.mark.parametrize("unreadable", _UNREADABLE)
async def test_one_unreadable_does_not_stop_the_round(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    domain: str,
    kind: str,
    unreadable: Any,
) -> None:
    """Test the round carries on past one Home Assistant cannot list.

    The other one in the same round still gets its issue, and the unreadable
    one is still read by Spook's own walker, so its other unknown reference
    is reported too.
    """
    key, ghost, phantom = _KINDS[kind]
    await _async_set_up(
        hass,
        domain,
        {
            "broken": _steps(key, unreadable, ghost),
            "healthy": [{"action": "light.turn_on", "target": {key: phantom}}],
        },
    )
    repair = importlib.import_module(
        f"custom_components.spook.ectoplasms.{domain}.repairs.unknown_{kind}_references"
    ).SpookRepair(hass)

    with caplog.at_level(logging.DEBUG, logger="custom_components.spook"):
        await repair.async_inspect()

    issue_registry = ir.async_get(hass)
    for alias, unknown in (("broken", ghost), ("healthy", phantom)):
        issue = async_issue_about(issue_registry, f"{repair.repair}_{domain}.{alias}")
        assert issue, f"no issue for {domain}.{alias}"
        assert issue.translation_placeholders
        assert unknown in issue.translation_placeholders[repair.reference_label]

    unlisted = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("Home Assistant could not list")
    ]
    assert len(unlisted) == 1
    assert f"{domain}.broken" in unlisted[0]


@pytest.mark.parametrize(
    ("repair_name", "key"),
    [
        ("empty_areas", "area_id"),
        ("empty_floors", "floor_id"),
        ("unused_labels", "label_id"),
    ],
)
async def test_one_unreadable_does_not_stop_the_empty_ones(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    repair_name: str,
    key: str,
) -> None:
    """Test an empty area, floor or label is still found past an unreadable one.

    Asking whether anything targets it used to go through Home Assistant's
    `automations_with_area` and its siblings, which ask every automation in
    one go and give up on the first they cannot read.
    """
    created = {
        "area_id": lambda: ar.async_get(hass).async_create("Attic").id,
        "floor_id": lambda: fr.async_get(hass).async_create("Attic").floor_id,
        "label_id": lambda: lr.async_get(hass).async_create("Attic").label_id,
    }[key]()
    freezer.tick(_AGED)
    await _async_set_up(
        hass, "automation", {"broken": [{"action": "light.turn_on", "data": {key: 42}}]}
    )
    repair = importlib.import_module(
        f"custom_components.spook.ectoplasms.homeassistant.repairs.{repair_name}"
    ).SpookRepair(hass)

    await repair.async_inspect()

    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{repair_name}_{created}")


async def test_helper_usage_counts_past_an_unreadable_one(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the helper fix flow still counts who uses it.

    It asked Home Assistant's `automations_with_entity`, which gives up on
    the first automation it cannot read, and the menu would not open.
    """
    entry = MockConfigEntry(domain="derivative", title="Ghostly")
    entry.add_to_hass(hass)
    helper = entity_registry.async_get_or_create(
        "sensor", "derivative", "x", config_entry=entry
    )
    await _async_set_up(
        hass,
        "automation",
        {
            "broken": [{"action": "light.turn_on", "data": {"entity_id": 42}}],
            "user": [
                {
                    "action": "homeassistant.update_entity",
                    "target": {"entity_id": helper.entity_id},
                }
            ],
        },
    )

    flow = HelperUnknownSourcesFixFlow()
    flow.hass = hass
    flow.data = {"helper_config_entry_id": entry.entry_id, "helper": "Ghostly"}

    menu = await flow.async_step_init()

    assert "1 automation" in menu["description_placeholders"]["usage"]


@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_usages_are_found_past_an_unreadable_one(
    hass: HomeAssistant, domain: str
) -> None:
    """Test finding where something is used still reads the unreadable one."""
    await _async_set_up(
        hass, domain, {"broken": _steps("entity_id", 42, "light.xghost")}
    )

    usages = await async_find_usages(hass, "light.xghost", ("entity",))

    assert [usage.id for usage in usages] == [f"{domain}.broken"]


@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_a_draft_home_assistant_cannot_list_is_still_checked(
    hass: HomeAssistant, domain: str
) -> None:
    """Test a draft is checked like a saved one, not refused for its data."""
    steps_key = "actions" if domain == "automation" else "sequence"
    draft = {steps_key: _steps("entity_id", 42, "light.xghost")}

    found = await async_check_draft(hass, domain, draft)

    assert found["entities"] == ["light.xghost"]
