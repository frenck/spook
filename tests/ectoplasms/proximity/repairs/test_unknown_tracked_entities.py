"""Tests for the proximity unknown tracked entities repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.proximity.repairs.unknown_tracked_entities import (
    SpookRepair,
)

from .conftest import async_set_up_proximity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


async def test_unknown_tracked_entity_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test proximity tracking something that no longer exists is reported.

    People rather than device trackers, since a device tracker comes and goes
    by nature and Spook never reports those as missing.
    """
    hass.states.async_set("person.here", "home")
    entry = await async_set_up_proximity(
        hass, tracked=["person.here", "person.moved_out"]
    )

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN, f"proximity_unknown_tracked_entities_{entry.entry_id}"
    )
    assert issue
    assert "person.moved_out" in issue.translation_placeholders["entities"]
    assert "person.here" not in issue.translation_placeholders["entities"]


async def test_tracked_entities_that_exist_are_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test proximity tracking only real entities is left alone."""
    hass.states.async_set("person.here", "home")
    entry = await async_set_up_proximity(hass, tracked=["person.here"])

    await SpookRepair(hass).async_inspect()

    assert not issue_registry.async_get_issue(
        DOMAIN, f"proximity_unknown_tracked_entities_{entry.entry_id}"
    )
