"""Tests for what automations and scripts name as an entity that is no entity ID.

Two places only, both of which Home Assistant first looks at while running:
the `entity_id` an action takes as data, and the literal a template lookup
is handed. Asked through the real repairs, on automations and scripts Home
Assistant loaded itself.
"""

# The two hooks a repair runs per entity are protected; this is a round of
# one, the way the draft check runs it.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.automation import UnavailableAutomationEntity
from homeassistant.components.script import UnavailableScriptEntity
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.draft_checking import async_check_draft
from custom_components.spook.ectoplasms.automation.repairs import (
    unknown_entity_references as automation_entities,
)
from custom_components.spook.ectoplasms.script.repairs import (
    unknown_entity_references as script_entities,
)
from custom_components.spook.ectoplasms.template.repairs import (
    unknown_entity_references as template_entities,
)
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

# The forum case: an attribute tacked onto the entity ID.
_FORUM_VALUE = "input_boolean.bedroom_blind.current_position"


def _config(kind: str, steps: list[Any], **extra: Any) -> dict[str, Any]:
    """Return an automation or a script running these steps."""
    if kind == "automation":
        return {
            "alias": "Spooky",
            "triggers": [{"trigger": "homeassistant", "event": "start"}],
            "actions": steps,
            **extra,
        }
    return {"alias": "Spooky", "sequence": steps, **extra}


async def _async_load(hass: HomeAssistant, kind: str, config: dict[str, Any]) -> Any:
    """Load one automation or script the way Home Assistant does."""
    assert await async_setup_component(hass, "input_boolean", {})
    assert await async_setup_component(hass, "homeassistant", {})
    hass.states.async_set("input_boolean.bedroom_blind", "on")
    hass.states.async_set("sensor.a", "on")

    if kind == "automation":
        loaded = {"automation": {"id": "spooky", **config}}
    else:
        loaded = {"script": {"spooky": config}}
    assert await async_setup_component(hass, kind, loaded)
    await hass.async_block_till_done()

    entity = hass.data[DATA_INSTANCES][kind].get_entity(f"{kind}.spooky")
    # Home Assistant loads it: nothing here is checked before it runs.
    assert not isinstance(
        entity, (UnavailableAutomationEntity, UnavailableScriptEntity)
    )
    return entity


async def _async_reported(
    hass: HomeAssistant, kind: str, steps: list[Any], **extra: Any
) -> set[str]:
    """Return what the entity repair reports for these steps."""
    entity = await _async_load(hass, kind, _config(kind, steps, **extra))

    repair = _REPAIRS[kind](hass)
    await repair._async_setup_inspection()
    return await repair._async_compute_unknown_references(entity)


def _turn_on(**fields: Any) -> dict[str, Any]:
    """Return a step turning on the bedroom blind's switch, written as given."""
    return {"action": "input_boolean.turn_on", **fields}


def _render(template: str) -> list[dict[str, Any]]:
    """Return a step that renders this template."""
    return [{"variables": {"rendered": template}}]


# Action data: Home Assistant only looks at it when the action runs.


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("data_key", ["data", "data_template"])
async def test_no_entity_id_as_action_data_is_reported(
    hass: HomeAssistant, kind: str, data_key: str
) -> None:
    """Test an `entity_id` in action data that is no entity ID is reported.

    The action refuses it when it runs, which is the first time Home
    Assistant looks. Said to be no entity ID, without a guess at what was
    meant, even with the switch it starts with right there.
    """
    steps = [_turn_on(**{data_key: {"entity_id": _FORUM_VALUE}})]

    assert await _async_reported(hass, kind, steps) == {_FORUM_VALUE}


async def test_the_action_refuses_it_when_it_runs(hass: HomeAssistant) -> None:
    """Test the premise: the script loads, and the action refuses the data."""
    await _async_load(
        hass,
        "script",
        _config("script", [_turn_on(data={"entity_id": _FORUM_VALUE})]),
    )

    with pytest.raises(vol.Invalid, match="entity_id"):
        await hass.services.async_call(
            "input_boolean", "turn_on", {"entity_id": _FORUM_VALUE}, blocking=True
        )


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (["input_boolean.bedroom_blind", "input boolean"], {"input boolean"}),
        ("input_boolean.bedroom_blind, input_boolean.a b", {"input_boolean.a b"}),
    ],
    ids=["list", "comma separated"],
)
async def test_each_entity_in_action_data_is_read(
    hass: HomeAssistant, kind: str, value: Any, expected: set[str]
) -> None:
    """Test a list and text with commas are read one entity at a time.

    Home Assistant takes text with commas as a list.
    """
    steps = [_turn_on(data={"entity_id": value})]

    assert await _async_reported(hass, kind, steps) == expected


@pytest.mark.parametrize("kind", _KINDS)
async def test_an_action_checking_entity_id_itself_is_read(
    hass: HomeAssistant, kind: str
) -> None:
    """Test an action asking for an entity ID without being an entity action.

    `homeassistant.turn_on` checks it with `cv.entity_ids` of its own.
    """
    steps = [{"action": "homeassistant.turn_on", "data": {"entity_id": "a b"}}]

    assert await _async_reported(hass, kind, steps) == {"a b"}


_BAD_DATA = {"entity_id": _FORUM_VALUE}


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "step",
    [
        _turn_on(target={"entity_id": "input_boolean.bedroom_blind"}, data=_BAD_DATA),
        _turn_on(entity_id="input_boolean.bedroom_blind", data=_BAD_DATA),
        _turn_on(
            target="{{ {'entity_id': 'input_boolean.bedroom_blind'} }}",
            data=_BAD_DATA,
        ),
        _turn_on(
            data_template="{{ {'entity_id': 'input_boolean.bedroom_blind'} }}",
            data=_BAD_DATA,
        ),
    ],
    ids=["target", "entity_id on the step", "templated target", "templated data"],
)
async def test_what_goes_over_the_data_wins(
    hass: HomeAssistant, kind: str, step: dict[str, Any]
) -> None:
    """Test an `entity_id` in data the action never gets is left alone.

    Home Assistant hands the action its target over whatever the data says,
    and rendered data may hold anything.
    """
    assert await _async_reported(hass, kind, [step]) == set()


@pytest.mark.parametrize("kind", _KINDS)
async def test_a_target_without_entities_leaves_the_data(
    hass: HomeAssistant, kind: str
) -> None:
    """Test a target naming only an area leaves the data's `entity_id` be."""
    steps = [_turn_on(target={"area_id": "bedroom"}, data=_BAD_DATA)]

    assert await _async_reported(hass, kind, steps) == {_FORUM_VALUE}


@pytest.mark.parametrize("kind", _KINDS)
async def test_data_template_goes_over_data(hass: HomeAssistant, kind: str) -> None:
    """Test the `entity_id` of `data_template` is the one the action gets."""
    steps = [
        _turn_on(
            data={"entity_id": "input boolean"},
            data_template={"entity_id": "input_boolean.bedroom_blind"},
        ),
        _turn_on(
            data={"entity_id": "input_boolean.bedroom_blind"},
            data_template={"entity_id": _FORUM_VALUE},
        ),
    ]

    assert await _async_reported(hass, kind, steps) == {_FORUM_VALUE}


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "action",
    ["my_integration.do_it", "script.another_one", "notify.nobody_here"],
    ids=["no schema", "a script called by name", "no such action"],
)
async def test_an_action_that_takes_anything_is_left_alone(
    hass: HomeAssistant, kind: str, action: str
) -> None:
    """Test an action that does not check `entity_id` is left alone.

    Without a schema it takes anything, a script takes it as a field of its
    own, and an action that does not exist is the action repair's.
    """
    hass.services.async_register("my_integration", "do_it", lambda _call: None)
    steps = [{"action": action, "data": {"entity_id": _FORUM_VALUE}}]

    assert await _async_reported(hass, kind, steps) == set()


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "value",
    [
        "{{ trigger.entity_id }}",
        ["{{ trigger.entity_id }}"],
        "{{ ['input_boolean.bedroom_blind', 'input_boolean.bedroom_blind'] | join(', ') }}",
        "[[entity]]",
        "Input_Boolean.Bedroom_Blind",
        "all",
        "NONE",
        "",
        "   ",
        "input_boolean.*",
        "this.entity_id.attributes",
        "trigger.entity_id.x",
        "group.living room",
    ],
)
async def test_what_the_entity_walk_lets_go_is_not_reported_in_data(
    hass: HomeAssistant, kind: str, value: Any
) -> None:
    """Test templates, capitals, all and none, patterns and the rest.

    A template is whatever it renders to. Home Assistant lower cases an ID
    first, and an ID with capitals is reported as written elsewhere.
    """
    steps = [_turn_on(data={"entity_id": value})]

    assert await _async_reported(hass, kind, steps) == set()


@pytest.mark.parametrize("kind", _KINDS)
async def test_a_disabled_step_is_not_read(hass: HomeAssistant, kind: str) -> None:
    """Test what only a disabled step names is not reported."""
    steps = [
        _turn_on(enabled=False, data={"entity_id": _FORUM_VALUE}),
        {
            "enabled": False,
            "variables": {"rendered": "{{ states('sensor.a.b') }}"},
        },
    ]

    assert await _async_reported(hass, kind, steps) == set()


@pytest.mark.parametrize("kind", _KINDS)
async def test_an_action_handed_over_as_a_value_is_not_read(
    hass: HomeAssistant, kind: str
) -> None:
    """Test something shaped like an action under a key that holds values.

    It is only a value somebody hands over, whatever its shape.
    """
    steps = [
        {
            "variables": {
                "later": {
                    "action": "input_boolean.turn_on",
                    "data": {"entity_id": _FORUM_VALUE},
                }
            }
        }
    ]

    assert await _async_reported(hass, kind, steps) == set()


async def test_somebody_s_own_event_payload_is_not_read(
    hass: HomeAssistant,
) -> None:
    """Test the payload of somebody's own event is left alone.

    Whatever the sender puts there, the entity repair leaves it be, and
    so does this.
    """
    config = {
        "alias": "Spooky",
        "triggers": [
            {
                "trigger": "event",
                "event_type": "my_remote_pressed",
                "event_data": {"which": "{{ states('sensor.a.b') }}"},
            }
        ],
        "actions": [{"event": "my_remote_relayed", "event_data": {"entity_id": "a b"}}],
    }
    entity = await _async_load(hass, "automation", config)

    repair = automation_entities.SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == set()


# Templates: a lookup handed something that is no entity ID finds nothing.


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "template",
    [
        "{{ states('sensor.a.b') }}",
        "{{ states('sensor.a.b', rounded=True) }}",
        "{{ states(entity_id='sensor.a.b') }}",
        "{{ is_state('sensor.a.b', 'on') }}",
        "{{ state_attr('sensor.a.b', 'unit') }}",
        "{{ is_state_attr('sensor.a.b', 'unit', 'W') }}",
        "{{ has_value('sensor.a.b') }}",
        "{{ state_translated('sensor.a.b') }}",
        "{{ state_attr_translated('sensor.a.b', 'unit') }}",
        "{{ 'sensor.a.b' | states }}",
        "{{ 'sensor.a.b' | state_attr('unit') }}",
        "{{ 'sensor.a.b' | has_value }}",
        "{{ 'sensor.a.b' | state_translated }}",
        "{{ 'sensor.a.b' | state_attr_translated('unit') }}",
        "{{ 'sensor.a.b' is has_value }}",
        "{{ 'sensor.a.b' is is_state('on') }}",
        "{{ 'sensor.a.b' is not is_state_attr('unit', 'W') }}",
        "{%- if states('sensor.a.b') == 'on' -%}yes{%- endif -%}",
    ],
)
async def test_a_lookup_of_no_entity_id_is_reported(
    hass: HomeAssistant, kind: str, template: str
) -> None:
    """Test every lookup taking one entity, called, as a filter and as a test."""
    assert await _async_reported(hass, kind, _render(template)) == {"sensor.a.b"}


@pytest.mark.parametrize(
    ("template", "rendered"),
    [
        ("{{ states('sensor.a.b') }}", "unknown"),
        ("{{ states('sensor') }}", "unknown"),
        ("{{ 'sensor' | states }}", "unknown"),
        ("{{ is_state('sensor.a.b', 'unknown') }}", False),
        ("{{ state_attr('sensor.a.b', 'unit') }}", None),
        ("{{ is_state_attr('sensor.a.b', 'unit', None) }}", False),
        ("{{ has_value('sensor.a.b') }}", False),
    ],
)
async def test_the_lookups_find_nothing(
    hass: HomeAssistant, template: str, rendered: Any
) -> None:
    """Test the premise: the lookup finds nothing, and says nothing about it.

    A bare domain is no exception for `states()`: only `states.sensor` and
    `states['sensor']` hand back a domain.
    """
    hass.states.async_set("sensor.a", "on", {"unit": "W"})

    assert Template(template, hass).async_render() == rendered


@pytest.mark.parametrize(
    "template",
    [
        "{{ state_translated('sensor.a.b') }}",
        "{{ state_attr_translated('sensor.a.b', 'unit') }}",
    ],
)
async def test_the_translated_lookups_raise(hass: HomeAssistant, template: str) -> None:
    """Test the premise: the translated lookups raise instead."""
    with pytest.raises(Exception, match="Invalid entity ID"):
        Template(template, hass).async_render()


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "template",
    ["{{ states('sensor') }}", "{{ 'sensor' | states }}"],
)
async def test_a_bare_domain_for_states_is_reported(
    hass: HomeAssistant, kind: str, template: str
) -> None:
    """Test `states('sensor')` is reported: called, it looks up an entity."""
    assert await _async_reported(hass, kind, _render(template)) == {"sensor"}


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "template",
    [
        "{{ states.sensor | count }}",
        "{{ states['sensor'] | count }}",
        "{{ states.sensor.a.attributes.unit }}",
        "{{ states.sensor.a_.state }}",
        "{{ states('sensor.' ~ which) }}",
        "{{ states('sensor.a' ~ '.b') }}",
        "{{ states(which) }}",
        "{{ states('Sensor.A') }}",
        "{{ states('all') }}",
        "{{ states('') }}",
        "{{ states('trigger.entity_id.x') }}",
        "{{ states('group.living room') }}",
        "{{ states('sensor.*') }}",
        "{{ expand('sensor.a.b') }}",
        "{{ closest('sensor.a.b') }}",
        "{{ device_id('sensor.a.b') }}",
        "{{ 'sensor.a.b' }}",
        "{# states('sensor.a.b') #}",
        "{% set states = my_states %}{{ states('sensor.a.b') }}",
    ],
)
async def test_what_is_no_lookup_of_a_literal_is_not_reported(
    hass: HomeAssistant, kind: str, template: str
) -> None:
    """Test domains, computed arguments, and what the walk lets go, left alone.

    `states.sensor` is a domain, and `states.sensor.a` names, whatever
    they spell. A computed
    argument is whatever it is at runtime. `expand` and `closest` take
    groups and lists as well, and the registry lookups take more than
    entity IDs.
    """
    assert await _async_reported(hass, kind, _render(template)) == set()


@pytest.mark.parametrize("kind", _KINDS)
async def test_a_name_the_configuration_gives_hides_the_call_only(
    hass: HomeAssistant, kind: str
) -> None:
    """Test a variable called `states` hides the call, never the filter.

    Filters and tests are Jinja's own registries.
    """
    steps = [
        {"variables": {"states": "{{ {} }}"}},
        *_render("{{ states('sensor.a.b') }}"),
        *_render("{{ 'sensor.c.d' | states }}"),
        *_render("{{ 'sensor.e.f' is has_value }}"),
    ]

    assert await _async_reported(hass, kind, steps) == {"sensor.c.d", "sensor.e.f"}


@pytest.mark.parametrize("kind", _KINDS)
async def test_text_that_is_only_shown_is_not_read(
    hass: HomeAssistant, kind: str
) -> None:
    """Test a description or an alias with an example template is left alone."""
    steps = [{"alias": "Uses {{ states('sensor.a.b') }}", "delay": 0}]

    assert (
        await _async_reported(
            hass, kind, steps, description="Like {{ states('sensor.c.d') }}"
        )
        == set()
    )


@pytest.mark.parametrize("kind", _KINDS)
async def test_a_template_in_a_trigger_or_condition_is_read(
    hass: HomeAssistant, kind: str
) -> None:
    """Test a template condition is rendered when it runs, and read here too."""
    steps = [{"condition": "template", "value_template": "{{ has_value('a.b.c') }}"}]

    assert await _async_reported(hass, kind, steps) == {"a.b.c"}


# The issue, and the draft check.


@pytest.mark.parametrize("kind", _KINDS)
async def test_the_issue_says_it_is_no_entity_id(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, kind: str
) -> None:
    """Test the issue lists it after the entities that do not exist.

    Said to be no entity ID, without a guess at what was meant.
    """
    steps = [
        _turn_on(target={"entity_id": "input_boolean.gone"}),
        _turn_on(data={"entity_id": _FORUM_VALUE}),
    ]
    await _async_load(hass, kind, _config(kind, steps))

    await _REPAIRS[kind](hass).async_inspect()

    issue = async_issue_about(
        issue_registry, f"{kind}_unknown_entity_references_{kind}.spooky"
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["entities"] == (
        f"- `input_boolean.gone`\n- `{_FORUM_VALUE}` (not an entity ID)"
    )


@pytest.mark.parametrize("kind", _KINDS)
async def test_a_draft_says_it_apart(hass: HomeAssistant, kind: str) -> None:
    """Test a draft lists it under `not_entity_ids`, like a dashboard draft."""
    assert await async_setup_component(hass, "input_boolean", {})
    steps = [
        _turn_on(target={"entity_id": "input_boolean.gone"}),
        _turn_on(data={"entity_id": _FORUM_VALUE}),
        *_render("{{ states('sensor.a.b') }}"),
    ]

    unknown = await async_check_draft(hass, kind, _config(kind, steps))

    assert unknown["entities"] == ["input_boolean.gone"]
    assert unknown["not_entity_ids"] == [_FORUM_VALUE, "sensor.a.b"]


# The template helpers keep their templates in the entry options.


async def test_a_template_helper_looking_up_no_entity_id_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a template helper's lookup of no entity ID, next to a missing one."""
    entry = MockConfigEntry(
        domain="template",
        title="Blind position",
        options={
            "name": "Blind position",
            "template_type": "sensor",
            "state": "{{ states('cover.bedroom_blind.current_position') }}",
            "availability": "{{ has_value('cover.gone') }}",
        },
    )
    entry.add_to_hass(hass)

    await template_entities.SpookRepair(hass).async_inspect()

    issue = async_issue_about(
        issue_registry, f"template_unknown_entity_references_{entry.entry_id}"
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["entities"] == (
        "- `cover.gone`\n- `cover.bedroom_blind.current_position` (not an entity ID)"
    )


async def test_a_template_helper_with_only_good_lookups_is_fine(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a template helper whose lookups are all fine raises nothing."""
    hass.states.async_set("cover.bedroom_blind", "open")
    entry = MockConfigEntry(
        domain="template",
        title="Blind position",
        options={
            "name": "Blind position",
            "template_type": "sensor",
            "state": "{{ state_attr('cover.bedroom_blind', 'current_position') }}",
        },
    )
    entry.add_to_hass(hass)

    await template_entities.SpookRepair(hass).async_inspect()

    assert (
        async_issue_about(
            issue_registry, f"template_unknown_entity_references_{entry.entry_id}"
        )
        is None
    )
