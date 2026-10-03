"""Tests for the unknown customized entities repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core_config import DATA_CUSTOMIZE
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.util import dt as dt_util

from custom_components.spook.entity_filtering import (
    async_setup_all_entity_ids_cache_invalidation,
)
from custom_components.spook.ectoplasms.homeassistant.repairs.unknown_customized_entities import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

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

    issue = async_issue_about(issue_registry, _ISSUE_ID)
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

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def test_no_customizations_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an empty customize section produces no issue."""
    hass.data[DATA_CUSTOMIZE] = EntityValues()

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def _let_the_debouncer_run(hass: HomeAssistant) -> None:
    """Move the clock past the repair's cooldown, and let its look finish."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_an_entity_a_script_sets_after_startup_clears_it(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entity arriving later, as a state only, is noticed.

    Entities a script sets never reach the entity registry, and often arrive
    well after Home Assistant started. The repair only looked again on a
    registry change or a configuration update, so the report stayed. #1622.
    """
    # Spook sets this up on start; without it the arrival is never seen.
    async_setup_all_entity_ids_cache_invalidation(hass)
    hass.data[DATA_CUSTOMIZE] = EntityValues(
        exact={"sensor.pv_status_today": {"icon": "mdi:solar-power"}}
    )
    repair = SpookRepair(hass)
    await repair.async_activate()
    # The look that activating lines up, done and out of the way first, so the
    # one after the entity arrives can only have been asked for by it.
    await _let_the_debouncer_run(hass)
    assert async_issue_about(issue_registry, _ISSUE_ID)

    hass.states.async_set("sensor.pv_status_today", "1.2")
    await _let_the_debouncer_run(hass)

    assert async_issue_about(issue_registry, _ISSUE_ID) is None

    await repair.async_deactivate()
