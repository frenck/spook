"""Tests for the unknown customized entities repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core_config import DATA_CUSTOMIZE
from homeassistant.helpers.entity_values import EntityValues

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs.unknown_customized_entities import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE_ID = "unknown_customized_entities_unknown_customized_entities"


async def test_unknown_customized_entity_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a customize entry for a non-existing entity is reported."""
    hass.states.async_set("light.known", "on")
    hass.data[DATA_CUSTOMIZE] = EntityValues(
        exact={
            "light.gone": {"icon": "mdi:ghost"},
            "light.known": {"icon": "mdi:lightbulb"},
        }
    )

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    entities = issue.translation_placeholders["entities"]
    assert "light.gone" in entities
    assert "light.known" not in entities


async def test_known_customized_entity_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a customize entry for an existing entity is left alone."""
    hass.states.async_set("light.known", "on")
    hass.data[DATA_CUSTOMIZE] = EntityValues(exact={"light.known": {"icon": "x"}})

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_no_customizations_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an empty customize section produces no issue."""
    hass.data[DATA_CUSTOMIZE] = EntityValues()

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None
