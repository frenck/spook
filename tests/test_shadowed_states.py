"""Tests for entities read from templates where `states` is not Home Assistant's.

A template can define its own `states`, with a macro or a `set`, and an
automation, a script or a template entity can hand its templates one, as a
variable or a field. Then `states.light.ghost.state` names no entity at all.
A filter is Jinja's own registry: `'light.ghost' | states` still is Home
Assistant's, whatever the names around it. Asked through the real repairs,
on configurations Home Assistant loaded itself.
"""

# The two hooks a repair runs per entity are protected; this is a round of
# one, the way the draft check runs it.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.automation import UnavailableAutomationEntity
from homeassistant.components.script import UnavailableScriptEntity
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.ectoplasms.automation.repairs import (
    unknown_entity_references as automation_entities,
)
from custom_components.spook.ectoplasms.script.repairs import (
    unknown_entity_references as script_entities,
)
from custom_components.spook.ectoplasms.template.repairs import (
    unknown_entity_references as template_entities,
)
from custom_components.spook.usage_finding import async_find_usages
from tests.repair_helpers import async_issue_about
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_KINDS = ("automation", "script")

_REPAIRS = {
    "automation": automation_entities.SpookRepair,
    "script": script_entities.SpookRepair,
}

# What a `states` of somebody's own could look like: names that read the
# way Home Assistant's do, so the template renders.
_OWN_STATES_VALUE = "{'light': {'ghost': {'state': 'on'}}}"
_OWN_STATES = "{{ " + _OWN_STATES_VALUE + " }}"

# Spelled out after `states.`: names, no literal. Only Home Assistant's
# `states` makes an entity out of them.
_SPELLED_OUT = "{{ states.light.ghost.state }}"


async def _async_load(
    hass: HomeAssistant, kind: str, steps: list[Any], **extra: Any
) -> Any:
    """Load an automation or a script running these steps, as Home Assistant does."""
    assert await async_setup_component(hass, "homeassistant", {})
    configurations = {
        "automation": {
            "id": "spooky",
            "alias": "Spooky",
            "triggers": [{"trigger": "homeassistant", "event": "start"}],
            "actions": steps,
            **extra,
        },
        "script": {"spooky": {"sequence": steps, **extra}},
    }
    assert await async_setup_component(hass, kind, {kind: configurations[kind]})
    await hass.async_block_till_done()

    entity = hass.data[DATA_INSTANCES][kind].get_entity(f"{kind}.spooky")
    assert not isinstance(
        entity, (UnavailableAutomationEntity, UnavailableScriptEntity)
    )
    return entity


async def _async_reported(
    hass: HomeAssistant, kind: str, steps: list[Any], **extra: Any
) -> set[str]:
    """Return what the entity repair reports for these steps."""
    entity = await _async_load(hass, kind, steps, **extra)

    repair = _REPAIRS[kind](hass)
    await repair._async_setup_inspection()
    return await repair._async_compute_unknown_references(entity)


def _render(template: str) -> dict[str, Any]:
    """Return a step that renders this template."""
    return {"variables": {"rendered": template}}


def _notify(template: str) -> dict[str, Any]:
    """Return a step that hands this template to an action as data."""
    return {
        "action": "persistent_notification.create",
        "data": {"message": template},
    }


# Automations and scripts.


@pytest.mark.parametrize("kind", _KINDS)
async def test_spelled_out_after_states_is_read(hass: HomeAssistant, kind: str) -> None:
    """Test the premise: with nothing else called `states`, it is an entity."""
    steps = [_render(_SPELLED_OUT), _notify("{{ states.light.ghost_message.state }}")]

    assert await _async_reported(hass, kind, steps) == {
        "light.ghost",
        "light.ghost_message",
    }


@pytest.mark.parametrize("kind", _KINDS)
async def test_only_the_root_states_spells_out_an_entity(
    hass: HomeAssistant, kind: str
) -> None:
    """Test `States.` and `obj.states.` are no lookups of Home Assistant's.

    Jinja names are case sensitive, and `obj.states` is an attribute of
    `obj`. The real `states.` still is, with an object ID in any case: Home
    Assistant tries that in lower case too.
    """
    steps = [
        _render("{{ States.light.ghost_capital.state }}"),
        _render(
            "{% set obj = {'states': " + _OWN_STATES_VALUE + "} %}"
            "{{ obj.states.light.ghost_attribute.state }}"
        ),
        _render("{{ states.light.Ghost_Mixed.state }}"),
    ]

    assert await _async_reported(hass, kind, steps) == {"light.ghost_mixed"}


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "template",
    [
        "{% macro states() %}on{% endmacro %}" + _SPELLED_OUT,
        "{% set states = " + _OWN_STATES_VALUE + " %}" + _SPELLED_OUT,
    ],
)
async def test_a_states_the_template_defines_names_no_entity(
    hass: HomeAssistant, kind: str, template: str
) -> None:
    """Test `states.light.ghost` reads the template's own `states`."""
    assert await _async_reported(hass, kind, [_render(template)]) == set()


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    ("where", "extra"),
    [
        ("variables", {"variables": {"states": _OWN_STATES}}),
        ("step", {}),
    ],
)
async def test_a_states_the_configuration_gives_names_no_entity(
    hass: HomeAssistant, kind: str, where: str, extra: dict[str, Any]
) -> None:
    """Test a variable called `states` hides the lookup, never the filter.

    Read from a template anywhere, and from one handed to an action as data
    too. `states('Light.Pump')` is not Home Assistant's lookup either, so it
    is not tried in lower case: it is no entity ID, and not reported.
    """
    steps = [
        _render(_SPELLED_OUT),
        _render("{{ states('Light.Pump') }}"),
        _notify("{{ states.light.ghost_message.state }}"),
        _render("{{ 'light.ghost_filter' | states }}"),
    ]
    if where == "step":
        steps.insert(0, {"variables": {"states": _OWN_STATES}})

    assert await _async_reported(hass, kind, steps, **extra) == {"light.ghost_filter"}


async def test_a_field_called_states_names_no_entity(hass: HomeAssistant) -> None:
    """Test a script field called `states` is the script's own `states`."""
    steps = [_render(_SPELLED_OUT), _notify("{{ states.light.ghost_message.state }}")]

    assert (
        await _async_reported(
            hass, "script", steps, fields={"states": {"description": "Own"}}
        )
        == set()
    )


@pytest.mark.parametrize("kind", _KINDS)
async def test_what_only_a_disabled_step_names_is_still_left_out(
    hass: HomeAssistant, kind: str
) -> None:
    """Test the reading with and without disabled steps honours the names too.

    `light.ghost` is only a target in a parked step. Read once more for the
    steps still running, `states.light.ghost` must not bring it back.
    """
    steps = [
        _render(_SPELLED_OUT),
        {
            "action": "homeassistant.turn_on",
            "target": {"entity_id": "light.ghost"},
            "enabled": False,
        },
    ]

    assert (
        await _async_reported(hass, kind, steps, variables={"states": _OWN_STATES})
        == set()
    )


@pytest.mark.parametrize("kind", _KINDS)
async def test_a_variable_in_a_disabled_step_hides_the_lookup_when_pruned(
    hass: HomeAssistant, kind: str
) -> None:
    """Test the names come from all of it, read without disabled steps too.

    The only `states` of its own is set in a parked step. Taken from what is
    left once that is pruned, `states.light.ghost` would bring back the
    target only the other parked step holds.
    """
    steps = [
        {"variables": {"states": _OWN_STATES}, "enabled": False},
        _render(_SPELLED_OUT),
        {
            "action": "homeassistant.turn_on",
            "target": {"entity_id": "light.ghost"},
            "enabled": False,
        },
    ]

    assert await _async_reported(hass, kind, steps) == set()


@pytest.mark.parametrize("kind", _KINDS)
async def test_a_template_in_home_assistants_own_list(
    hass: HomeAssistant, kind: str
) -> None:
    """Test a template Home Assistant's own list hands over is read the same way.

    A list of templates as the `entity_id` in action data comes back from
    Home Assistant's own list as it is, and is read once more.
    """
    template = "{{ 'light.kitchen' if states.light.ghost.state else 'light.hall' }}"
    steps = [{"action": "homeassistant.turn_on", "data": {"entity_id": [template]}}]

    assert await _async_reported(
        hass, kind, steps, variables={"states": _OWN_STATES}
    ) == {"light.kitchen", "light.hall"}


@pytest.mark.parametrize("kind", _KINDS)
async def test_a_literal_is_read_whatever_it_is_handed_to(
    hass: HomeAssistant, kind: str
) -> None:
    """Test a literal handed to a `states` of the template's own is still read.

    Every literal shaped like an entity ID is, whatever takes it, like one
    in a `set` or handed to a macro of any other name. A macro called
    `states` can hand it on to the `states` filter, which is still Home
    Assistant's.
    """
    template = (
        "{% macro states(entity) %}{{ entity | states }}{% endmacro %}"
        "{{ states('light.ghost') }}"
    )

    assert await _async_reported(hass, kind, [_render(template)]) == {"light.ghost"}


@pytest.mark.parametrize("kind", _KINDS)
async def test_finding_usages_reads_it_the_same_way(
    hass: HomeAssistant, kind: str
) -> None:
    """Test finding where an entity is used agrees with the repair."""
    await _async_load(
        hass,
        kind,
        [_render(_SPELLED_OUT), _notify("{{ states.light.ghost.state }}")],
        variables={"states": _OWN_STATES},
    )

    assert await async_find_usages(hass, "light.ghost", ("entity",)) == []


# Template helpers, and template entities from YAML.


@pytest.mark.parametrize(
    "own_states",
    [
        "{% macro states() %}on{% endmacro %}",
        "{% set states = " + _OWN_STATES_VALUE + " %}",
    ],
)
async def test_a_template_helper_with_its_own_states(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, own_states: str
) -> None:
    """Test a template helper's own `states` hides the lookup, not the filter."""
    entry = MockConfigEntry(
        domain="template",
        title="Haunted",
        options={
            "name": "Haunted",
            "template_type": "sensor",
            "state": (
                own_states
                + "{{ states.sensor.ghost.state }}"
                + "{{ 'sensor.ghost_filter' | states }}"
            ),
        },
    )
    entry.add_to_hass(hass)

    await template_entities.SpookRepair(hass).async_inspect()

    issue = async_issue_about(
        issue_registry, f"template_unknown_entity_references_{entry.entry_id}"
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["entities"] == "- `sensor.ghost_filter`"


async def test_a_template_helper_action_with_a_variable_called_states(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a variable called `states` in a helper's action hides the lookup."""
    entry = MockConfigEntry(
        domain="template",
        title="Haunted",
        options={
            "name": "Haunted",
            "template_type": "button",
            "press": [
                {"variables": {"states": _OWN_STATES}},
                _notify(_SPELLED_OUT + "{{ 'light.ghost_filter' | states }}"),
            ],
        },
    )
    entry.add_to_hass(hass)

    await template_entities.SpookRepair(hass).async_inspect()

    issue = async_issue_about(
        issue_registry, f"template_unknown_entity_references_{entry.entry_id}"
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["entities"] == "- `light.ghost_filter`"


async def test_finding_usages_reads_a_template_helper_the_same_way(
    hass: HomeAssistant,
) -> None:
    """Test finding where an entity is used agrees for a template helper."""
    MockConfigEntry(
        domain="template",
        title="Haunted",
        options={
            "name": "Haunted",
            "template_type": "button",
            "press": [{"variables": {"states": _OWN_STATES}}, _notify(_SPELLED_OUT)],
        },
    ).add_to_hass(hass)

    assert await async_find_usages(hass, "light.ghost", ("entity",)) == []


async def _async_yaml_entities(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    section: dict[str, Any],
    entity_id: str = "sensor.haunted",
) -> str:
    """Return the entities the issue about one YAML template entity lists."""
    assert await async_setup_component(hass, "template", {"template": [section]})
    await hass.async_block_till_done()

    await template_entities.SpookRepair(hass).async_inspect()

    issue = async_issue_about(
        issue_registry, f"template_unknown_entity_references_{entity_id}"
    )
    assert issue
    assert issue.translation_placeholders
    return issue.translation_placeholders["entities"]


async def test_a_template_entity_with_a_variable_called_states(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a template entity's variable called `states` hides the lookup."""
    section = {
        "variables": {"states": _OWN_STATES},
        "sensor": {
            "name": "Haunted",
            "state": _SPELLED_OUT + "{{ 'sensor.ghost_filter' | states }}",
        },
    }

    assert (
        await _async_yaml_entities(hass, issue_registry, section)
        == "- `sensor.ghost_filter`"
    )


async def test_a_trigger_based_section_with_a_variable_called_states(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the actions of the section read the variable the same way."""
    section = {
        "triggers": [{"trigger": "event", "event_type": "spook"}],
        "variables": {"states": _OWN_STATES},
        "actions": [_notify("{{ states.sensor.ghost_message.state }}")],
        "sensor": {
            "name": "Haunted",
            "state": _SPELLED_OUT + "{{ 'sensor.ghost_filter' | states }}",
        },
    }

    assert (
        await _async_yaml_entities(hass, issue_registry, section)
        == "- `sensor.ghost_filter`"
    )


async def test_a_template_entitys_own_action_with_a_variable_called_states(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an action of the entity's own reads the variable the same way."""
    section = {
        "variables": {"states": _OWN_STATES},
        "switch": {
            "name": "Haunted",
            "state": "{{ 'switch.ghost_filter' | states }}",
            "turn_on": [_notify("{{ states.switch.ghost_message.state }}")],
            "turn_off": [],
        },
    }

    assert (
        await _async_yaml_entities(hass, issue_registry, section, "switch.haunted")
        == "- `switch.ghost_filter`"
    )


async def test_a_variable_in_a_disabled_step_hides_the_lookup_both_times(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the names come from all of it, read with and without disabled steps.

    Every name a configuration gives counts, disabled steps too. Taken from
    what is left once those are pruned, the template would count as active
    only because the step naming its variable is parked.
    """
    section = {
        "triggers": [{"trigger": "event", "event_type": "spook"}],
        "actions": [
            {"variables": {"states": _OWN_STATES}, "enabled": False},
            _notify("{{ states.sensor.ghost_message.state }}"),
        ],
        "sensor": {
            "name": "Haunted",
            "state": _SPELLED_OUT + "{{ 'sensor.ghost_filter' | states }}",
        },
    }

    assert (
        await _async_yaml_entities(hass, issue_registry, section)
        == "- `sensor.ghost_filter`"
    )
