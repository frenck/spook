"""Tests for the dead entities repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_RESTORED, STATE_UNAVAILABLE

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs.dead_entities import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er, issue_registry as ir


def _loaded_entry(hass: HomeAssistant, title: str = "Hue") -> MockConfigEntry:
    """Add a loaded config entry to hass."""
    entry = MockConfigEntry(domain="derivative", title=title)
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry


def _register_restored(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry | None,
    object_id: str,
) -> str:
    """Register an entity with a restored unavailable state."""
    reg = entity_registry.async_get_or_create(
        "sensor",
        "hue",
        object_id,
        config_entry=entry,
    )
    hass.states.async_set(reg.entity_id, STATE_UNAVAILABLE, {ATTR_RESTORED: True})
    return reg.entity_id


async def test_dead_entity_of_loaded_entry_is_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a restored entity of a loaded entry is reported."""
    entry = _loaded_entry(hass)
    dead = _register_restored(hass, entity_registry, entry, "dead")

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["entities"] == f"- `{dead}`"
    assert issue.translation_placeholders["integration"] == "Hue"


async def test_live_entity_is_not_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entity with a real state is not reported."""
    entry = _loaded_entry(hass)
    reg = entity_registry.async_get_or_create(
        "sensor", "hue", "live", config_entry=entry
    )
    hass.states.async_set(reg.entity_id, "21")

    await SpookRepair(hass).async_inspect()

    assert (
        issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
        is None
    )


async def test_restored_entity_of_retrying_entry_is_not_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a restored entity of a retrying entry is not reported.

    A config entry that has not finished loading may still provide the
    entity, so it must not be flagged as dead.
    """
    entry = MockConfigEntry(domain="derivative", title="Hue")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)
    _register_restored(hass, entity_registry, entry, "maybe")

    await SpookRepair(hass).async_inspect()

    assert (
        issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
        is None
    )


async def test_restored_entity_without_config_entry_is_not_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a restored entity with no config entry is not reported.

    Without a config entry its load state cannot be confirmed, so it is
    deliberately left alone.
    """
    _register_restored(hass, entity_registry, None, "yamlish")

    await SpookRepair(hass).async_inspect()

    assert not any(
        issue_id.startswith("dead_entities_")
        for domain, issue_id in issue_registry.issues
        if domain == DOMAIN
    )
