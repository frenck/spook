"""Tests for the table-driven unknown helper source references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest

from custom_components.spook import repairs
from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs.unknown_helper_source_references import (
    SpookRepair,
)
from custom_components.spook.repairs import (
    HelperUnknownSourcesFixFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er, issue_registry as ir


def _issue_id(entry: MockConfigEntry) -> str:
    """Return the Spook issue ID for a helper config entry."""
    return f"unknown_helper_source_references_{entry.entry_id}"


@pytest.mark.parametrize(
    ("helper_domain", "options"),
    [
        pytest.param(
            "derivative",
            {"name": "Ghostly", "source": "sensor.ghost"},
            id="single-key-source",
        ),
        pytest.param(
            "generic_thermostat",
            {"name": "Ghostly", "target_sensor": "sensor.ghost", "heater": "switch.x"},
            id="multi-key",
        ),
    ],
)
async def test_unknown_source_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    helper_domain: str,
    options: dict[str, Any],
) -> None:
    """Test a helper referencing a nonexistent source is reported."""
    entry = MockConfigEntry(domain=helper_domain, title="Ghostly", options=options)
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue
    assert issue.translation_placeholders
    assert "sensor.ghost" in issue.translation_placeholders["sources"]
    assert issue.translation_placeholders["domain"] == helper_domain


async def test_known_source_creates_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a helper referencing an existing entity is not reported."""
    hass.states.async_set("sensor.real", "1")

    entry = MockConfigEntry(
        domain="derivative",
        title="Fine",
        options={"name": "Fine", "source": "sensor.real"},
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None


async def test_source_stored_as_registry_id_is_resolved(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test sources stored as registry IDs resolve to their entity ID.

    Some helpers (like switch_as_x) store the registry ID rather than the
    entity ID; a live one must not be reported, a dead one must be.
    """
    live = entity_registry.async_get_or_create("sensor", "demo", "live")
    hass.states.async_set(live.entity_id, "1")

    live_entry = MockConfigEntry(
        domain="derivative",
        title="Live",
        options={"name": "Live", "source": live.id},
    )
    live_entry.add_to_hass(hass)

    dead_entry = MockConfigEntry(
        domain="derivative",
        title="Dead",
        options={"name": "Dead", "source": "deleted-registry-id"},
    )
    dead_entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(live_entry)) is None
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(dead_entry))


async def test_unrelated_config_entries_are_ignored(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test config entries outside the helper table are not inspected."""
    entry = MockConfigEntry(
        domain="hue",
        title="Bridge",
        options={"source": "sensor.ghost"},
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None


async def test_bayesian_observation_subentry_is_inspected(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test bayesian observations, stored as config subentries, are checked."""
    entry = MockConfigEntry(
        domain="bayesian",
        title="Ghostly",
        options={"name": "Ghostly"},
        subentries_data=[
            {
                "subentry_type": "observation",
                "title": "Ghost seen",
                "unique_id": None,
                "data": {"entity_id": "sensor.ghost", "platform": "state"},
            },
        ],
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue
    assert issue.translation_placeholders
    assert "sensor.ghost" in issue.translation_placeholders["sources"]


async def test_bayesian_without_subentries_does_not_crash(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a bayesian entry with no observation subentries is fine."""
    entry = MockConfigEntry(
        domain="bayesian",
        title="Odd",
        options={"name": "Odd"},
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None


async def test_issue_is_fixable_with_config_entry_data(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue is fixable and carries the config entry id."""
    entry = MockConfigEntry(
        domain="derivative",
        title="Ghostly",
        options={"name": "Ghostly", "source": "sensor.ghost"},
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue
    assert issue.is_fixable
    assert issue.data
    assert issue.data["helper_config_entry_id"] == entry.entry_id


async def test_fix_flow_remove_deletes_helper(
    hass: HomeAssistant,
) -> None:
    """Test the remove option removes the whole helper config entry."""
    entry = MockConfigEntry(
        domain="derivative",
        title="Ghostly",
        options={"name": "Ghostly", "source": "sensor.ghost"},
    )
    entry.add_to_hass(hass)

    flow = await async_create_fix_flow(
        hass,
        _issue_id(entry),
        {"helper_config_entry_id": entry.entry_id, "helper": "Ghostly"},
    )
    assert isinstance(flow, HelperUnknownSourcesFixFlow)
    flow.hass = hass
    flow.data = {"helper_config_entry_id": entry.entry_id}

    result = await flow.async_step_remove()

    assert result["type"] == "create_entry"
    assert hass.config_entries.async_get_entry(entry.entry_id) is None


async def test_menu_warns_when_used_by_automation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the menu warns, honestly, when the helper is still in use."""
    entry = MockConfigEntry(domain="derivative", title="Ghostly")
    entry.add_to_hass(hass)
    reg = entity_registry.async_get_or_create(
        "sensor", "derivative", "x", config_entry=entry
    )
    monkeypatch.setattr(
        repairs,
        "automations_with_entity",
        lambda _hass, eid: ["automation.a"] if eid == reg.entity_id else [],
    )

    flow = HelperUnknownSourcesFixFlow()
    flow.hass = hass
    flow.data = {"helper_config_entry_id": entry.entry_id, "helper": "Ghostly"}

    menu = await flow.async_step_init()
    usage = menu["description_placeholders"]["usage"]
    assert "1 automation" in usage
    assert "Spook will then point out" in usage


async def test_menu_reports_when_unused(
    hass: HomeAssistant,
) -> None:
    """Test the menu states the helper is unused when it is."""
    entry = MockConfigEntry(domain="derivative", title="Ghostly")
    entry.add_to_hass(hass)

    flow = HelperUnknownSourcesFixFlow()
    flow.hass = hass
    flow.data = {"helper_config_entry_id": entry.entry_id, "helper": "Ghostly"}

    menu = await flow.async_step_init()
    usage = menu["description_placeholders"]["usage"]
    assert usage == "It is not used by any automation or script."
