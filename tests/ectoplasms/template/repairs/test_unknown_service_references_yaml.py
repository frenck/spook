"""Tests for unknown action references in template entities from YAML."""

# The cleanup round is what clears a fixed issue, and there is no public way
# to it.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.template.configuration import (
    EVENT_TEMPLATE_RELOADED,
)
from custom_components.spook.ectoplasms.template.repairs import (
    unknown_service_references,
)
from custom_components.spook.ectoplasms.template.repairs.unknown_service_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

PREFIX = "template_unknown_service_references"
GHOST = [{"action": "script.ghost"}]
TRIGGER = {"trigger": "event", "event_type": "spook_test"}


async def _setup(hass: HomeAssistant, *sections: dict[str, Any]) -> None:
    """Set up template entities the way `template:` in YAML does."""
    assert await async_setup_component(hass, "template", {"template": list(sections)})
    await hass.async_block_till_done()


def _issue(issue_registry: ir.IssueRegistry, entity_id: str) -> ir.IssueEntry | None:
    """Return the issue about a template entity, if there is one."""
    return async_issue_about(issue_registry, f"{PREFIX}_{entity_id}")


def _services(issue_registry: ir.IssueRegistry, entity_id: str) -> str:
    """Return the actions the issue about a template entity lists."""
    issue = _issue(issue_registry, entity_id)
    assert issue
    assert issue.translation_placeholders
    return issue.translation_placeholders["services"]


async def test_unknown_action_in_template_switch_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a template switch from YAML calling a missing action is reported."""
    await _setup(
        hass,
        {
            "switch": {
                "name": "Haunted",
                "state": "{{ true }}",
                "turn_on": GHOST,
                "turn_off": [],
            }
        },
    )

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, "switch.haunted")
    assert issue
    assert issue.translation_key == f"{PREFIX}_yaml"
    assert issue.issue_domain == "template"
    assert (
        issue.learn_more_url == "https://spook.boo/template#unknown-referenced-actions"
    )
    assert issue.translation_placeholders == {
        "services": "- `script.ghost`",
        "name": "Haunted",
        "entity_id": "switch.haunted",
    }


@pytest.mark.parametrize(
    ("platform", "config", "entity_id"),
    [
        pytest.param(
            "switch",
            {"state": "{{ true }}", "turn_on": [], "turn_off": GHOST},
            "switch.haunted",
            id="switch turn_off",
        ),
        pytest.param(
            "button",
            {"press": GHOST},
            "button.haunted",
            id="button press",
        ),
        pytest.param(
            "number",
            {"state": "1", "step": 1, "set_value": GHOST},
            "number.haunted",
            id="number set_value",
        ),
        pytest.param(
            "select",
            {"state": "a", "options": "{{ ['a', 'b'] }}", "select_option": GHOST},
            "select.haunted",
            id="select select_option",
        ),
        pytest.param(
            "lock",
            {"state": "{{ true }}", "lock": [], "unlock": GHOST},
            "lock.haunted",
            id="lock unlock",
        ),
        pytest.param(
            "cover",
            {"state": "open", "open_cover": GHOST, "close_cover": []},
            "cover.haunted",
            id="cover open_cover",
        ),
        pytest.param(
            "light",
            {"state": "{{ true }}", "turn_on": [], "turn_off": [], "set_level": GHOST},
            "light.haunted",
            id="light set_level",
        ),
        pytest.param(
            "fan",
            {
                "state": "{{ true }}",
                "turn_on": [],
                "turn_off": [],
                "preset_mode": "{{ 'auto' }}",
                "preset_modes": ["auto", "eco"],
                "set_preset_mode": GHOST,
            },
            "fan.haunted",
            id="fan set_preset_mode next to a list of modes",
        ),
    ],
)
async def test_every_action_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    platform: str,
    config: dict[str, Any],
    entity_id: str,
) -> None:
    """Test every action a template entity has of its own is read."""
    await _setup(hass, {platform: {"name": "Haunted", **config}})
    assert hass.states.get(entity_id)

    await SpookRepair(hass).async_inspect()

    assert _services(issue_registry, entity_id) == "- `script.ghost`"


async def test_trigger_based_section_actions_are_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the actions of a trigger based section go to each of its entities."""
    await _setup(
        hass,
        {
            "triggers": [TRIGGER],
            "actions": GHOST,
            "sensor": [{"name": "First", "state": "1"}],
            "binary_sensor": [{"name": "Second", "state": "on"}],
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _services(issue_registry, "sensor.first") == "- `script.ghost`"
    assert _services(issue_registry, "binary_sensor.second") == "- `script.ghost`"


async def test_existing_actions_are_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test template entities calling actions that exist are fine."""
    hass.services.async_register("script", "real", lambda _: None)
    real = [{"action": "script.real"}]
    await _setup(
        hass,
        {"switch": {"name": "Fine", "turn_on": real, "turn_off": real}},
        {
            "triggers": [TRIGGER],
            "actions": real,
            "sensor": {"name": "Fine", "state": "1"},
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "switch.fine") is None
    assert _issue(issue_registry, "sensor.fine") is None


async def test_attribute_called_action_is_not_an_action(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute named action is a value it shows, nothing it calls."""
    await _setup(
        hass,
        {
            "sensor": {
                "name": "Pointer",
                "state": "1",
                "attributes": {"action": "script.ghost"},
            }
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "sensor.pointer") is None


async def test_templated_and_disabled_actions_are_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test what is only known at runtime, or never runs, is left alone.

    The same as for template helpers.
    """
    await _setup(
        hass,
        {
            "button": {
                "name": "Quiet",
                "press": [
                    {"action": "{{ 'script.' ~ 'ghost' }}"},
                    {"action": "script.ghost", "enabled": False},
                ],
            }
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "button.quiet") is None


async def test_one_issue_per_entity_with_only_its_own_findings(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test entities sharing a section are not blamed for each other.

    Home Assistant hands each state based entity the whole section it came
    from as well, which is not what it runs.
    """
    await _setup(
        hass,
        {
            "button": [
                {"name": "Haunted", "press": GHOST},
                {"name": "Fine", "press": []},
            ]
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _services(issue_registry, "button.haunted") == "- `script.ghost`"
    assert _issue(issue_registry, "button.fine") is None


async def test_template_helpers_keep_their_own_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a template helper made in the UI is not read as YAML as well."""
    entry = MockConfigEntry(
        domain="template",
        title="Ghostly button",
        options={"name": "Ghostly button", "template_type": "button", "press": GHOST},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("button.ghostly_button")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, f"{PREFIX}_{entry.entry_id}")
    assert _issue(issue_registry, "button.ghostly_button") is None


async def test_reload_is_looked_at(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fixing a template entity and reloading clears its issue."""
    hass.services.async_register("script", "real", lambda _: None)
    await _setup(hass, {"button": {"name": "Haunted", "press": GHOST}})

    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, "button.haunted")

    fixed = {
        "template": [
            {"button": {"name": "Haunted", "press": [{"action": "script.real"}]}}
        ]
    }
    with patch("homeassistant.config.load_yaml_config_file", return_value=fixed):
        await hass.services.async_call("template", "reload", blocking=True)
        await hass.async_block_till_done()

    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, "button.haunted") is None


async def test_reloaded_while_waiting_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an entity reloaded while the event loop had its turn is skipped.

    What was read is a configuration it no longer has. Reloading starts
    another round, which looks at the new one.
    """
    haunted = {"button": {"name": "Haunted", "press": GHOST}}
    await _setup(hass, haunted)

    async def _reloading(_: float) -> None:
        with patch(
            "homeassistant.config.load_yaml_config_file",
            return_value={"template": [haunted]},
        ):
            await hass.services.async_call("template", "reload", blocking=True)
            await hass.async_block_till_done()

    monkeypatch.setattr(
        unknown_service_references,
        "asyncio",
        SimpleNamespace(sleep=_reloading),
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "button.haunted") is None

    # Read again, the new configuration is looked at as usual.
    monkeypatch.setattr(unknown_service_references, "asyncio", asyncio)
    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "button.haunted")


async def test_template_reloaded_event_makes_it_look(
    hass: HomeAssistant,
) -> None:
    """Test the event a template reload ends with starts a look."""
    repair = SpookRepair(hass)
    await repair.async_activate()
    await hass.async_block_till_done()

    with patch.object(repair.inspect_debouncer, "async_call") as call:
        hass.bus.async_fire(EVENT_TEMPLATE_RELOADED)
        await hass.async_block_till_done()

    assert call.called
    await repair.async_deactivate()
