"""Tests for the proximity unknown ignored zones repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.spook.ectoplasms.proximity.repairs.unknown_ignored_zones import (
    SpookRepair,
)

from .conftest import async_set_up_proximity
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


async def test_unknown_ignored_zone_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test proximity ignoring a zone that no longer exists is reported."""
    entry = await async_set_up_proximity(hass, ignored_zones=["zone.demolished"])

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(
        issue_registry, f"proximity_unknown_ignored_zones_{entry.entry_id}"
    )
    assert issue
    assert "zone.demolished" in issue.translation_placeholders["zones"]


async def test_ignored_zones_that_exist_are_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test proximity ignoring only real zones is left alone."""
    entry = await async_set_up_proximity(hass, ignored_zones=["zone.home"])

    await SpookRepair(hass).async_inspect()

    assert not async_issue_about(
        issue_registry, f"proximity_unknown_ignored_zones_{entry.entry_id}"
    )
