"""Tests for the min/max unknown sources repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs.min_max_unknown_sources import (
    SpookRepair,
)
from custom_components.spook.repairs import (
    MinMaxUnknownSourcesFixFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


def _entry(hass: HomeAssistant, members: list[str]) -> MockConfigEntry:
    """Add a min/max helper config entry with the given members."""
    entry = MockConfigEntry(
        domain="min_max",
        title="Combined",
        options={"entity_ids": members, "type": "max"},
    )
    entry.add_to_hass(hass)
    return entry


def _issue_id(entry: MockConfigEntry) -> str:
    """Return the registry issue id for a helper entry."""
    return f"min_max_unknown_sources_{entry.entry_id}"


async def test_unknown_member_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a min/max helper with a missing member is reported as fixable."""
    hass.states.async_set("sensor.known", "1")
    entry = _entry(hass, ["sensor.known", "sensor.gone"])

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue
    assert issue.is_fixable
    assert issue.data
    assert issue.data["min_max_config_entry_id"] == entry.entry_id
    assert "sensor.gone" in issue.data["sources"]
    assert "sensor.known" not in issue.data["sources"]


async def test_deleted_registry_member_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a registry ID whose entry is gone is reported."""
    entry = _entry(hass, ["01JGONEREGISTRYIDXXXXXXXXX"])

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry))


async def test_all_known_members_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a helper whose members all exist is left alone."""
    hass.states.async_set("sensor.known", "1")
    entry = _entry(hass, ["sensor.known"])

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None


async def test_fix_flow_remove_prunes_members(
    hass: HomeAssistant,
) -> None:
    """Test the remove option drops the missing members from the helper."""
    hass.states.async_set("sensor.known", "1")
    hass.states.async_set("sensor.two", "2")
    entry = _entry(hass, ["sensor.known", "sensor.two", "sensor.gone"])

    flow = await async_create_fix_flow(
        hass,
        _issue_id(entry),
        {
            "min_max_config_entry_id": entry.entry_id,
            "helper": "Combined",
            "sources": "x",
        },
    )
    assert isinstance(flow, MinMaxUnknownSourcesFixFlow)
    flow.hass = hass
    flow.data = {"min_max_config_entry_id": entry.entry_id}

    result = await flow.async_step_remove()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["entity_ids"] == ["sensor.known", "sensor.two"]


async def test_fix_flow_remove_keeps_minimum_members(
    hass: HomeAssistant,
) -> None:
    """Test pruning that would leave fewer than two members is refused."""
    hass.states.async_set("sensor.known", "1")
    entry = _entry(hass, ["sensor.known", "sensor.gone"])

    flow = MinMaxUnknownSourcesFixFlow()
    flow.hass = hass
    flow.issue_id = _issue_id(entry)
    flow.data = {"min_max_config_entry_id": entry.entry_id}

    result = await flow.async_step_remove()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "too_few_members"
    # The helper is left untouched.
    assert entry.options["entity_ids"] == ["sensor.known", "sensor.gone"]


async def test_remove_stops_the_helper_listening(hass: HomeAssistant) -> None:
    """Test a source that was removed cannot come back and drive the value.

    Runs the real min/max integration, because the stored options being right
    is not the same as the helper being right. Without a reload the helper
    keeps listening to the source somebody just took out, so the day that
    source returns it decides the value again while the configuration says it
    is gone.
    """
    hass.states.async_set("sensor.one", "10", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.two", "20", {"unit_of_measurement": "W"})
    assert await async_setup_component(hass, "min_max", {})

    entry = MockConfigEntry(
        domain="min_max",
        title="Combined",
        options={
            "name": "Combined",
            "entity_ids": ["sensor.one", "sensor.two", "sensor.gone"],
            "type": "max",
            "round_digits": 2,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = MinMaxUnknownSourcesFixFlow()
    flow.hass = hass
    flow.data = {
        "min_max_config_entry_id": entry.entry_id,
        "helper": "Combined",
        "sources": "- `sensor.gone`",
    }
    result = await flow.async_step_remove()
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["entity_ids"] == ["sensor.one", "sensor.two"]
    assert hass.states.get("sensor.combined").state == "20.0"

    # The source somebody just took out returns, higher than the two that are
    # left. If the helper is still listening, it wins.
    hass.states.async_set("sensor.gone", "99", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()

    assert hass.states.get("sensor.combined").state == "20.0"
