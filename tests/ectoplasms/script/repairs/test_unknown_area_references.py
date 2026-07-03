"""Tests for the script unknown area references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.helpers.entity_component import DATA_INSTANCES

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.script.repairs.unknown_area_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import area_registry as ar, issue_registry as ir


async def test_script_with_unknown_area_creates_issue(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a script referencing a nonexistent area raises an issue."""
    area = area_registry.async_create("Upstairs")

    entity = SimpleNamespace(
        entity_id="script.spooky",
        name="Spooky",
        unique_id="spooky",
        script=SimpleNamespace(referenced_areas={area.id, "ghost_area"}),
    )
    hass.data[DATA_INSTANCES] = {"script": SimpleNamespace(entities=[entity])}

    repair = SpookRepair(hass)
    await repair.async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        "script_unknown_area_references_script.spooky",
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["areas"] == "- `ghost_area`"
    assert issue.translation_placeholders["edit"] == "/config/script/edit/spooky"
