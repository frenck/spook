"""Tests for unknown attribute references in template entities from YAML."""

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
    unknown_attribute_references,
)
from custom_components.spook.ectoplasms.template.repairs.unknown_attribute_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

    from custom_components.spook.attribute_checking import UnknownAttribute

PREFIX = "template_unknown_attribute_references"

# A difference in case alone is reported without asking the recorder, which
# keeps these tests about reading the configuration.
WRONG = "{{ state_attr('light.kitchen', 'Brightness') }}"
FOUND = "- `Brightness` of `light.kitchen` (did you mean `brightness`?)"
TRIGGER = {"trigger": "event", "event_type": "spook"}


@pytest.fixture(autouse=True)
def _kitchen(hass: HomeAssistant) -> None:
    """Have a light with a brightness."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})


async def _setup(hass: HomeAssistant, *sections: dict[str, Any]) -> None:
    """Set up template entities the way `template:` in YAML does."""
    assert await async_setup_component(hass, "template", {"template": list(sections)})
    await hass.async_block_till_done()


def _issue(issue_registry: ir.IssueRegistry, entity_id: str) -> ir.IssueEntry | None:
    """Return the issue about a template entity, if there is one."""
    return async_issue_about(issue_registry, f"{PREFIX}_{entity_id}")


def _attributes(issue_registry: ir.IssueRegistry, entity_id: str) -> str:
    """Return the attributes the issue about a template entity lists."""
    issue = _issue(issue_registry, entity_id)
    assert issue
    assert issue.translation_placeholders
    return issue.translation_placeholders["attributes"]


async def test_state_based_entity_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a state based template entity reading a wrong attribute."""
    await _setup(hass, {"sensor": {"name": "Haunted", "state": WRONG}})

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, "sensor.haunted")
    assert issue
    assert issue.translation_key == f"{PREFIX}_yaml"
    assert issue.issue_domain == "template"
    assert (
        issue.learn_more_url
        == "https://spook.boo/template#unknown-referenced-attributes"
    )
    assert issue.translation_placeholders == {
        "attributes": FOUND,
        "name": "Haunted",
        "entity_id": "sensor.haunted",
    }


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"state": WRONG}, id="state"),
        pytest.param({"state": "1", "availability": WRONG}, id="availability"),
        pytest.param({"state": "1", "attributes": {"glow": WRONG}}, id="attributes"),
        pytest.param({"state": "1", "icon": WRONG}, id="icon"),
        pytest.param({"state": "1", "picture": WRONG}, id="picture"),
        pytest.param(
            {"state": "{{ glow }}", "variables": {"glow": WRONG}}, id="variables"
        ),
    ],
)
async def test_every_template_field_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
) -> None:
    """Test each template of a template entity is read."""
    await _setup(hass, {"sensor": {"name": "Haunted", **config}})

    await SpookRepair(hass).async_inspect()

    assert _attributes(issue_registry, "sensor.haunted") == FOUND


@pytest.mark.parametrize(
    ("section", "own"),
    [
        pytest.param(
            {
                "triggers": [
                    {
                        "trigger": "state",
                        "entity_id": "light.kitchen",
                        "attribute": "Brightness",
                    }
                ]
            },
            {},
            id="trigger",
        ),
        pytest.param(
            {
                "triggers": [TRIGGER],
                "conditions": [
                    {
                        "condition": "state",
                        "entity_id": "light.kitchen",
                        "attribute": "Brightness",
                        "state": "255",
                    }
                ],
            },
            {},
            id="condition",
        ),
        pytest.param(
            {"triggers": [TRIGGER], "actions": [{"wait_template": WRONG}]},
            {},
            id="action",
        ),
        pytest.param(
            {"triggers": [TRIGGER], "variables": {"glow": WRONG}},
            {},
            id="variables",
        ),
        pytest.param({"triggers": [TRIGGER]}, {"state": WRONG}, id="state"),
        pytest.param(
            {"triggers": [TRIGGER]},
            {
                "conditions": [
                    {
                        "condition": "state",
                        "entity_id": "light.kitchen",
                        "attribute": "Brightness",
                        "state": "255",
                    }
                ]
            },
            id="conditions of its own",
        ),
    ],
)
async def test_trigger_based_entity_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    section: dict[str, Any],
    own: dict[str, Any],
) -> None:
    """Test a trigger based entity is read with what its section shares."""
    await _setup(hass, {**section, "sensor": {"name": "Haunted", "state": "1", **own}})

    await SpookRepair(hass).async_inspect()

    assert _attributes(issue_registry, "sensor.haunted") == FOUND


async def test_known_attributes_are_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test template entities reading what the entity has are fine."""
    right = "{{ state_attr('light.kitchen', 'brightness') }}"
    await _setup(
        hass,
        {"sensor": {"name": "Fine", "state": right}},
        {
            "triggers": [
                {
                    "trigger": "state",
                    "entity_id": "light.kitchen",
                    "attribute": "brightness",
                }
            ],
            "sensor": {"name": "Fine trigger", "state": right},
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "sensor.fine") is None
    assert _issue(issue_registry, "sensor.fine_trigger") is None


async def test_attributes_named_like_a_condition_are_not_one(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test attributes the entity is given are not read as a condition."""
    await _setup(
        hass,
        {
            "sensor": {
                "name": "Haunted",
                "state": "1",
                "attributes": {
                    "condition": "state",
                    "entity_id": "light.kitchen",
                    "attribute": "Brightness",
                },
            }
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "sensor.haunted") is None


async def test_this_and_trigger_are_not_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test what a template is handed at runtime is not checked."""
    await _setup(
        hass,
        {
            "sensor": {
                "name": "Self aware",
                "state": "{{ state_attr(this.entity_id, 'Brightness') }}",
                "attributes": {"previous": "{{ this.attributes.Brightness }}"},
            }
        },
        {
            "triggers": [{"trigger": "state", "entity_id": "light.kitchen"}],
            "sensor": {
                "name": "Triggered",
                "state": "{{ trigger.to_state.attributes.Brightness }}",
            },
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "sensor.self_aware") is None
    assert _issue(issue_registry, "sensor.triggered") is None


@pytest.mark.parametrize(
    "section",
    [
        pytest.param(
            {
                "sensor": {
                    "name": "Shadowed",
                    "state": WRONG,
                    "variables": {"state_attr": 1},
                }
            },
            id="variables of its own",
        ),
        pytest.param(
            {
                "variables": {"state_attr": 1},
                "sensor": {"name": "Shadowed", "state": WRONG},
            },
            id="variables of the section",
        ),
        pytest.param(
            {
                "triggers": [TRIGGER],
                "variables": {"state_attr": 1},
                "sensor": {"name": "Shadowed", "state": WRONG},
            },
            id="variables of a trigger based section",
        ),
    ],
)
async def test_a_variable_hides_the_lookup(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    section: dict[str, Any],
) -> None:
    """Test a variable named like the lookup makes it no lookup at all."""
    await _setup(hass, section)

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, "sensor.shadowed") is None


async def test_one_issue_per_entity_with_only_its_own_findings(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test entities sharing a section are not blamed for each other."""
    await _setup(
        hass,
        {
            "sensor": [
                {"name": "Haunted", "state": WRONG},
                {
                    "name": "Fine",
                    "state": "{{ state_attr('light.kitchen', 'brightness') }}",
                },
            ]
        },
    )

    await SpookRepair(hass).async_inspect()

    assert _attributes(issue_registry, "sensor.haunted") == FOUND
    assert _issue(issue_registry, "sensor.fine") is None


async def test_template_helpers_keep_their_own_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a template helper made in the UI is not read as YAML as well."""
    entry = MockConfigEntry(
        domain="template",
        title="Haunted",
        options={"name": "Haunted", "template_type": "sensor", "state": WRONG},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.haunted")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, f"{PREFIX}_{entry.entry_id}")
    assert _issue(issue_registry, "sensor.haunted") is None


def _reload_with(fixed: dict[str, Any]) -> Any:
    """Return what makes a template reload read this configuration."""
    return patch(
        "homeassistant.config.load_yaml_config_file",
        return_value={"template": [fixed]},
    )


async def test_fixed_and_reloaded_is_cleared(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue goes once the entity is fixed and reloaded.

    Also what the repair remembers of an entity: a reload hands it a new
    configuration, which is read again rather than taken from the last round.
    """
    await _setup(hass, {"sensor": {"name": "Haunted", "state": WRONG}})
    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, "sensor.haunted")

    right = "{{ state_attr('light.kitchen', 'brightness') }}"
    with _reload_with({"sensor": {"name": "Haunted", "state": right}}):
        await hass.services.async_call("template", "reload", blocking=True)
        await hass.async_block_till_done()

    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, "sensor.haunted") is None


async def test_reloaded_while_asking_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an entity reloaded while the recorder was asked is not reported.

    What was found is about a configuration it no longer has. Reloading
    starts another round, which looks at the new one.
    """
    await _setup(hass, {"sensor": {"name": "Haunted", "state": WRONG}})
    ask = unknown_attribute_references.async_unknown_attributes

    async def _asking(
        hass: HomeAssistant, pairs: Iterable[tuple[str, str]]
    ) -> set[UnknownAttribute]:
        found = await ask(hass, pairs)
        with _reload_with({"sensor": {"name": "Haunted", "state": WRONG}}):
            await hass.services.async_call("template", "reload", blocking=True)
            await hass.async_block_till_done()
        return found

    monkeypatch.setattr(
        unknown_attribute_references, "async_unknown_attributes", _asking
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
