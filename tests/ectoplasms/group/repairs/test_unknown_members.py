"""Tests for the group unknown members repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM
from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.group.repairs.unknown_members import SpookRepair
from custom_components.spook.repairs import (
    GroupUnknownMembersFixFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er, issue_registry as ir

_ISSUE_ID = "group_unknown_members_light.living"


def _install_group(hass: HomeAssistant, entity_id: str, members: list[str]) -> None:
    """Install a fake UI group entity into the group entity platform."""
    entity = SimpleNamespace(entity_id=entity_id, name="Living", _entity_ids=members)
    hass.data[DATA_ENTITY_PLATFORM] = {
        "group": [SimpleNamespace(domain="light", entities={entity_id: entity})]
    }


async def test_unknown_member_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a group with a missing member is reported as fixable."""
    hass.states.async_set("light.known", "on")
    _install_group(hass, "light.living", ["light.known", "light.gone"])

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.is_fixable
    assert issue.data
    assert issue.data["group_entity_id"] == "light.living"
    assert "light.gone" in issue.data["entities"]
    assert "light.known" not in issue.data["entities"]


async def test_group_with_known_members_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a group whose members all exist is left alone."""
    hass.states.async_set("light.known", "on")
    _install_group(hass, "light.living", ["light.known"])

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_fix_flow_remove_prunes_ui_group(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the remove option drops missing members from a UI group."""
    hass.states.async_set("light.known", "on")
    entry = MockConfigEntry(
        domain="group",
        options={"entities": ["light.known", "light.gone"], "group_type": "light"},
    )
    entry.add_to_hass(hass)
    reg = entity_registry.async_get_or_create(
        "light", "group", "living", config_entry=entry
    )

    flow = await async_create_fix_flow(
        hass,
        f"group_unknown_members_{reg.entity_id}",
        {"group_entity_id": reg.entity_id, "group": "Living", "entities": "x"},
    )
    assert isinstance(flow, GroupUnknownMembersFixFlow)
    flow.hass = hass
    flow.data = {"group_entity_id": reg.entity_id, "group": "Living", "entities": "x"}

    # The menu names the group and its entity id.
    menu = await flow.async_step_init()
    assert menu["description_placeholders"] == {
        "group": "Living",
        "entity_id": reg.entity_id,
        "entities": "x",
    }

    result = await flow.async_step_remove()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["entities"] == ["light.known"]


async def test_fix_flow_remove_yaml_group_aborts(
    hass: HomeAssistant,
) -> None:
    """Test a YAML group (no config entry) reports it cannot be edited."""
    flow = GroupUnknownMembersFixFlow()
    flow.hass = hass
    flow.issue_id = "group_unknown_members_light.yaml_group"
    flow.data = {
        "group_entity_id": "light.yaml_group",
        "group": "YAML",
        "entities": "x",
    }

    result = await flow.async_step_remove()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_editable"


async def test_remove_reloads_the_running_group(hass: HomeAssistant) -> None:
    """Test the group that is running loses the member, not just the options.

    Runs the real group integration rather than a stand-in, because the whole
    question is whether the entity Home Assistant is serving changed. Nothing
    in the group integration listens for its own entry changing, so writing
    the options and stopping there leaves the member in the group until a
    restart, while the button says it is done.
    """
    hass.states.async_set("light.real", "on")
    assert await async_setup_component(hass, "group", {})

    entry = MockConfigEntry(
        domain="group",
        title="Hallway",
        options={
            "group_type": "light",
            "name": "Hallway",
            "entities": ["light.real", "light.gone"],
            "hide_members": False,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("light.hallway").attributes["entity_id"] == [
        "light.real",
        "light.gone",
    ]

    flow = GroupUnknownMembersFixFlow()
    flow.hass = hass
    flow.data = {
        "group_entity_id": "light.hallway",
        "group": "Hallway",
        "entities": "- `light.gone`",
    }
    result = await flow.async_step_remove()
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["entities"] == ["light.real"]
    assert hass.states.get("light.hallway").attributes["entity_id"] == ["light.real"]
