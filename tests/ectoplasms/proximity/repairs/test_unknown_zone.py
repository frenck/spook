"""Tests for the proximity unknown zone repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.proximity.repairs.unknown_zone import (
    SpookRepair,
)

from .conftest import async_set_up_proximity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


async def test_unknown_zone_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test proximity watching a zone that no longer exists is reported."""
    entry = await async_set_up_proximity(hass, zone="zone.demolished")

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN, f"proximity_unknown_zone_{entry.entry_id}"
    )
    assert issue
    assert issue.translation_placeholders["zone"] == "zone.demolished"


async def test_a_zone_that_exists_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test proximity watching a real zone is left alone."""
    entry = await async_set_up_proximity(hass, zone="zone.home")

    await SpookRepair(hass).async_inspect()

    assert not issue_registry.async_get_issue(
        DOMAIN, f"proximity_unknown_zone_{entry.entry_id}"
    )
