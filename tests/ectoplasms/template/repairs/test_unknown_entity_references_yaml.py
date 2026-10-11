"""Tests for unknown entity references in template entities from YAML."""

# The cleanup round is what an issue keyed to its findings needs looking at,
# and there is no public way to it.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.template.configuration import (
    EVENT_TEMPLATE_RELOADED,
)
from custom_components.spook.ectoplasms.template.repairs import (
    unknown_entity_references,
)
from custom_components.spook.ectoplasms.template.repairs.unknown_entity_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

PREFIX = "template_unknown_entity_references"


async def _setup(hass: HomeAssistant, *sections: dict[str, Any]) -> None:
    """Set up template entities the way `template:` in YAML does."""
    assert await async_setup_component(hass, "template", {"template": list(sections)})
    await hass.async_block_till_done()


def _issue(issue_registry: ir.IssueRegistry, entity_id: str) -> ir.IssueEntry | None:
    """Return the issue about a template entity, if there is one."""
    return async_issue_about(issue_registry, f"{PREFIX}_{entity_id}")


def _entities(issue_registry: ir.IssueRegistry, entity_id: str) -> str:
    """Return the entities the issue about a template entity lists."""
    issue = _issue(issue_registry, entity_id)
    assert issue
    assert issue.translation_placeholders
    return issue.translation_placeholders["entities"]


async def test_unknown_entity_in_state_based_entity_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a state based template entity naming a missing entity is reported."""
    await _setup(
        hass,
        {
            "sensor": {
                "name": "Haunted",
                "state": "{{ states('sensor.ghost') }}",
            }
        },
    )

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, "sensor.haunted")
    assert issue
    assert issue.translation_key == f"{PREFIX}_yaml"
    assert issue.issue_domain == "template"
    assert (
        issue.learn_more_url == "https://spook.boo/template#unknown-referenced-entities"
    )
    assert issue.translation_placeholders == {
        "entities": "- `sensor.ghost`",
        "name": "Haunted",
        "entity_id": "sensor.haunted",
    }


@pytest.mark.parametrize(
    ("platform", "config"),
    [
        pytest.param(
            "sensor",
            {"state": "{{ states('sensor.ghost') }}"},
            id="state",
        ),
        pytest.param(
            "sensor",
            {"state": "1", "availability": "{{ has_value('sensor.ghost') }}"},
            id="availability",
        ),
        pytest.param(
            "sensor",
            {"state": "1", "attributes": {"spirit": "{{ states('sensor.ghost') }}"}},
            id="attributes",
        ),
        pytest.param(
            "sensor",
            {
                "state": "1",
                "icon": "{{ 'mdi:ghost' if is_state('sensor.ghost', 'on') }}",
            },
            id="icon",
        ),
        pytest.param(
            "sensor",
            {"state": "1", "picture": "{{ state_attr('sensor.ghost', 'picture') }}"},
            id="picture",
        ),
        pytest.param(
            "sensor",
            {
                "state": "{{ spirit }}",
                "variables": {"spirit": "{{ states('sensor.ghost') }}"},
            },
            id="variables",
        ),
        pytest.param(
            "binary_sensor",
            {"state": "{{ is_state('sensor.ghost', 'on') }}"},
            id="binary sensor",
        ),
        pytest.param(
            "switch",
            {
                "state": "{{ true }}",
                "turn_on": [
                    {"action": "light.turn_on", "target": {"entity_id": "sensor.ghost"}}
                ],
                "turn_off": [],
            },
            id="action of its own",
        ),
    ],
)
async def test_every_template_field_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    platform: str,
    config: dict[str, Any],
) -> None:
    """Test each place a template entity can name an entity is read."""
    await _setup(hass, {platform: {"name": "Haunted", **config}})

    await SpookRepair(hass).async_inspect()

    assert _entities(issue_registry, f"{platform}.haunted") == "- `sensor.ghost`"


async def test_section_variables_of_a_state_based_entity_are_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the variables of a section reach the entities in it."""
    await _setup(
        hass,
        {
            "variables": {"spirit": "{{ states('sensor.ghost') }}"},
            "sensor": {"name": "Haunted", "state": "{{ spirit }}"},
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _entities(issue_registry, "sensor.haunted") == "- `sensor.ghost`"


TRIGGER = {"trigger": "event", "event_type": "spook"}


@pytest.mark.parametrize(
    "section",
    [
        pytest.param(
            {"triggers": [{"trigger": "state", "entity_id": "sensor.ghost"}]},
            id="trigger",
        ),
        pytest.param(
            {
                "triggers": [
                    {
                        "trigger": "template",
                        "value_template": "{{ is_state('sensor.ghost', 'on') }}",
                    }
                ]
            },
            id="template trigger",
        ),
        pytest.param(
            {
                "triggers": [TRIGGER],
                "conditions": [
                    {"condition": "state", "entity_id": "sensor.ghost", "state": "on"}
                ],
            },
            id="condition",
        ),
        pytest.param(
            {
                "triggers": [TRIGGER],
                "actions": [
                    {"action": "light.turn_on", "target": {"entity_id": "sensor.ghost"}}
                ],
            },
            id="action",
        ),
        pytest.param(
            {
                "triggers": [TRIGGER],
                "variables": {"spirit": "{{ states('sensor.ghost') }}"},
            },
            id="variables",
        ),
    ],
)
async def test_trigger_based_section_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    section: dict[str, Any],
) -> None:
    """Test what a trigger based section shares with its entity is read."""
    hass.services.async_register("light", "turn_on", lambda _: None)
    await _setup(hass, {**section, "sensor": {"name": "Haunted", "state": "1"}})

    await SpookRepair(hass).async_inspect()

    assert _entities(issue_registry, "sensor.haunted") == "- `sensor.ghost`"


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"state": "{{ states('sensor.ghost') }}"}, id="state"),
        pytest.param(
            {
                "state": "1",
                "conditions": [
                    {"condition": "state", "entity_id": "sensor.ghost", "state": "on"}
                ],
            },
            id="conditions of its own",
        ),
        pytest.param(
            {
                "state": "{{ spirit }}",
                "variables": {"spirit": "{{ states('sensor.ghost') }}"},
            },
            id="variables of its own",
        ),
    ],
)
async def test_trigger_based_entity_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
) -> None:
    """Test what a trigger based entity was given itself is read."""
    await _setup(hass, {"triggers": [TRIGGER], "sensor": {"name": "Haunted", **config}})

    await SpookRepair(hass).async_inspect()

    assert _entities(issue_registry, "sensor.haunted") == "- `sensor.ghost`"


async def test_existing_entities_are_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test template entities naming what exists are fine."""
    hass.states.async_set("sensor.real", "1")
    await _setup(
        hass,
        {
            "sensor": {
                "name": "Fine",
                "state": "{{ states('sensor.real') }}",
                "availability": "{{ has_value('sensor.real') }}",
                "attributes": {"also": "{{ states('sensor.real') }}"},
            }
        },
        {
            "triggers": [{"trigger": "state", "entity_id": "sensor.real"}],
            "conditions": [
                {"condition": "state", "entity_id": "sensor.real", "state": "1"}
            ],
            "sensor": {"name": "Fine trigger", "state": "{{ states('sensor.real') }}"},
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "sensor.fine") is None
    assert _issue(issue_registry, "sensor.fine_trigger") is None


async def test_this_and_trigger_are_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test what a template gets handed at runtime is no entity to look for."""
    hass.states.async_set("sensor.real", "1")
    await _setup(
        hass,
        {
            "sensor": {
                "name": "Self aware",
                "state": "{{ states(this.entity_id) }}",
                "attributes": {"previous": "{{ this.state }}"},
            }
        },
        {
            "triggers": [{"trigger": "state", "entity_id": "sensor.real"}],
            "variables": {"source": "{{ trigger.entity_id }}"},
            "sensor": {
                "name": "Triggered",
                "state": "{{ trigger.to_state.state if trigger.to_state else this.state }}",
                "attributes": {"from": "{{ states(source) }}"},
            },
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "sensor.self_aware") is None
    assert _issue(issue_registry, "sensor.triggered") is None


async def test_attribute_called_entity_id_is_not_an_action(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute named entity_id is a value it shows, nothing it calls."""
    await _setup(
        hass,
        {
            "sensor": {
                "name": "Pointer",
                "state": "1",
                "attributes": {"entity_id": "sensor.ghost"},
            }
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "sensor.pointer") is None


async def test_one_issue_per_entity_with_only_its_own_findings(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test entities sharing a section are not blamed for each other.

    Home Assistant hands each state based entity the whole section it came
    from as well, which is not what it renders.
    """
    hass.states.async_set("sensor.real", "1")
    await _setup(
        hass,
        {
            "sensor": [
                {"name": "Haunted", "state": "{{ states('sensor.ghost') }}"},
                {"name": "Fine", "state": "{{ states('sensor.real') }}"},
            ]
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _entities(issue_registry, "sensor.haunted") == "- `sensor.ghost`"
    assert _issue(issue_registry, "sensor.fine") is None


async def test_section_findings_go_to_each_of_its_entities(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a broken trigger is reported on every entity it leaves stale."""
    await _setup(
        hass,
        {
            "triggers": [{"trigger": "state", "entity_id": "sensor.ghost"}],
            "sensor": [{"name": "First", "state": "1"}],
            "binary_sensor": [{"name": "Second", "state": "on"}],
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _entities(issue_registry, "sensor.first") == "- `sensor.ghost`"
    assert _entities(issue_registry, "binary_sensor.second") == "- `sensor.ghost`"


async def test_disabled_trigger_is_said_to_be_disabled(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test what only a disabled trigger names is reported as harmless."""
    await _setup(
        hass,
        {
            "triggers": [
                TRIGGER,
                {"trigger": "state", "entity_id": "sensor.ghost", "enabled": False},
            ],
            "sensor": {"name": "Haunted", "state": "1"},
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _entities(issue_registry, "sensor.haunted") == (
        "- `sensor.ghost` (only referenced from disabled steps)"
    )


async def test_template_helpers_keep_their_own_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a template helper made in the UI is not read as YAML as well."""
    entry = MockConfigEntry(
        domain="template",
        title="Ghostly sensor",
        options={
            "name": "Ghostly sensor",
            "template_type": "sensor",
            "state": "{{ states('sensor.ghost') }}",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ghostly_sensor")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, f"{PREFIX}_{entry.entry_id}")
    assert _issue(issue_registry, "sensor.ghostly_sensor") is None


async def test_reload_is_looked_at(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fixing a template entity and reloading clears its issue."""
    hass.states.async_set("sensor.real", "1")
    await _setup(
        hass, {"sensor": {"name": "Haunted", "state": "{{ states('sensor.ghost') }}"}}
    )

    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, "sensor.haunted")

    fixed = {
        "template": [
            {"sensor": {"name": "Haunted", "state": "{{ states('sensor.real') }}"}}
        ]
    }
    with patch("homeassistant.config.load_yaml_config_file", return_value=fixed):
        await hass.services.async_call("template", "reload", blocking=True)
        await hass.async_block_till_done()

    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, "sensor.haunted") is None


async def test_reloaded_while_describing_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an entity reloaded while its findings were described is not reported.

    What was found is about a configuration it no longer has. Reloading
    starts another round, which looks at the new one.
    """
    haunted = {"sensor": {"name": "Haunted", "state": "{{ states('sensor.ghost') }}"}}
    await _setup(hass, haunted)
    describe = unknown_entity_references.async_describe_unknown_entities

    async def _describing(
        hass: HomeAssistant, entity_ids: Iterable[str], **kwargs: Any
    ) -> str:
        described = await describe(hass, entity_ids, **kwargs)
        with patch(
            "homeassistant.config.load_yaml_config_file",
            return_value={"template": [haunted]},
        ):
            await hass.services.async_call("template", "reload", blocking=True)
            await hass.async_block_till_done()
        return described

    monkeypatch.setattr(
        unknown_entity_references, "async_describe_unknown_entities", _describing
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "sensor.haunted") is None


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
