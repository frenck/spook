"""Tests for finding the states a configuration names."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.spook.reference_extraction import (
    extract_state_references_from_config,
)
from custom_components.spook.template_extraction import (
    extract_state_pairs_from_template,
)
from tests.template_configs import shadowing_configs


def _condition(**extra: Any) -> dict[str, Any]:
    """Return a state condition on the kitchen light being On."""
    return {
        "condition": "state",
        "entity_id": "light.kitchen",
        "state": "On",
        **extra,
    }


def _trigger(**extra: Any) -> dict[str, Any]:
    """Return a state trigger on the kitchen light."""
    return {"trigger": "state", "entity_id": "light.kitchen", **extra}


PAIR = {("light.kitchen", "On")}
ON_AND_DIMMED = {("light.kitchen", "On"), ("light.kitchen", "Dimmed")}


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"triggers": [_trigger(to="On")]}, id="to"),
        pytest.param({"triggers": [_trigger(**{"from": "On"})]}, id="from"),
        pytest.param({"triggers": [_trigger(not_to="On")]}, id="not to"),
        pytest.param({"triggers": [_trigger(not_from="On")]}, id="not from"),
        pytest.param({"triggers": [_trigger(to=["On"])]}, id="list"),
        pytest.param(
            {
                "trigger": [
                    {"platform": "state", "entity_id": "light.kitchen", "to": "On"}
                ]
            },
            id="legacy trigger",
        ),
        pytest.param({"conditions": [_condition()]}, id="condition"),
        pytest.param({"conditions": [_condition(state=["On"])]}, id="condition list"),
        pytest.param(
            {"conditions": [{"condition": "not", "conditions": [_condition()]}]},
            id="not",
        ),
        pytest.param(
            {"actions": [{"choose": [{"conditions": [_condition()], "sequence": []}]}]},
            id="choose",
        ),
        pytest.param(
            {"actions": [{"repeat": {"until": [_condition()], "sequence": []}}]},
            id="repeat until",
        ),
        pytest.param({"sequence": [_condition()]}, id="script condition step"),
        pytest.param(
            {"sequence": [{"wait_for_trigger": [_trigger(to="On")]}]},
            id="wait for trigger",
        ),
        pytest.param(
            {
                "conditions": [
                    {
                        "condition": "template",
                        "value_template": "{{ is_state('light.kitchen', 'On') }}",
                    }
                ]
            },
            id="template condition",
        ),
        pytest.param(
            {
                "conditions": [
                    {
                        "condition": "template",
                        "value_template": "{{ states('light.kitchen') == 'On' }}",
                    }
                ]
            },
            id="template comparison",
        ),
        pytest.param(
            {
                "actions": [
                    {
                        "action": "notify.notify",
                        "data": {
                            "message": "{{ is_state('light.kitchen', 'On') }}",
                        },
                    }
                ]
            },
            id="template in action data",
        ),
    ],
)
def test_state_references_are_found(config: dict[str, Any]) -> None:
    """Test every place a state can be named is read."""
    assert extract_state_references_from_config(config).pairs == PAIR


def test_every_entity_and_state_makes_a_pair() -> None:
    """Test several entities and several states make a pair each."""
    config = {
        "triggers": [
            {
                "trigger": "state",
                "entity_id": ["light.kitchen", "light.hall"],
                "from": "On",
                "to": ["Off", "off"],
            }
        ]
    }

    assert extract_state_references_from_config(config).pairs == {
        ("light.kitchen", "On"),
        ("light.kitchen", "Off"),
        ("light.kitchen", "off"),
        ("light.hall", "On"),
        ("light.hall", "Off"),
        ("light.hall", "off"),
    }


@pytest.mark.parametrize(
    "config",
    [
        # Home Assistant refuses anything but text, so such a trigger never
        # loads: nothing to say about what it waits for.
        pytest.param({"triggers": [_trigger(to=True)]}, id="yaml boolean"),
        pytest.param({"triggers": [_trigger(to=1)]}, id="number"),
        pytest.param({"triggers": [_trigger(to=[True, 1.5])]}, id="list of others"),
        pytest.param({"conditions": [_condition(state=True)]}, id="condition boolean"),
        # Any change, or any state.
        pytest.param({"triggers": [_trigger(to=None)]}, id="null"),
        pytest.param({"triggers": [_trigger(to="*")]}, id="match all"),
        pytest.param({"triggers": [_trigger(to="")]}, id="empty"),
        pytest.param({"triggers": [_trigger(to="{{ which }}")]}, id="templated"),
        # The state of the helper it names, not something written out.
        pytest.param(
            {"conditions": [_condition(state="input_select.mode")]},
            id="input helper in a condition",
        ),
        # The values of an attribute, not states.
        pytest.param(
            {"triggers": [_trigger(attribute="mode", to="On")]}, id="attribute trigger"
        ),
        pytest.param(
            {"conditions": [_condition(attribute="mode")]}, id="attribute condition"
        ),
        pytest.param(
            {
                "triggers": [
                    {
                        "trigger": "numeric_state",
                        "entity_id": "light.kitchen",
                        "above": 1,
                    }
                ]
            },
            id="numeric state",
        ),
        pytest.param({"conditions": [_condition(enabled=False)]}, id="disabled"),
        pytest.param(
            {"conditions": [_condition(entity_id="{{ which }}")]},
            id="templated entity",
        ),
        pytest.param(
            {
                "actions": [
                    {
                        "action": "script.turn_on",
                        "data": {"variables": {"check": _condition()}},
                    }
                ]
            },
            id="payload, not a condition",
        ),
        pytest.param(
            {
                "description": "{{ is_state('light.kitchen', 'On') }}",
                "actions": [],
            },
            id="description",
        ),
    ],
)
def test_state_references_left_alone(config: dict[str, Any]) -> None:
    """Test what is not a state written out, or does not run, is left out."""
    references = extract_state_references_from_config(config)
    assert not references.pairs
    assert not references.followed


def test_spook_state_trigger_is_handed_back_whole() -> None:
    """Test Spook's own trigger comes back as it is, with each state it names.

    Following an attribute, its `to` names that attribute's values. Text
    only, like Home Assistant's own trigger.
    """
    named = {
        "trigger": "spook.state_changed",
        "options": {"domain": ["light"], "to": ["On"], "not_from": "off"},
    }
    following = {
        "trigger": "spook.state_changed",
        "options": {"domain": ["light"], "attribute": "mode", "to": ["On"]},
    }
    not_text = {
        "trigger": "spook.state_changed",
        "options": {"domain": ["light"], "to": [True]},
    }

    references = extract_state_references_from_config(
        {"triggers": [named, following, not_text]}
    )

    assert sorted(state for _config, state in references.followed) == ["On", "off"]
    assert all(config == named for config, _state in references.followed)
    assert not references.pairs


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{ is_state('light.kitchen', 'On') }}", PAIR),
        ('{{ is_state("light.kitchen","On") }}', PAIR),
        ("{% if is_state('light.kitchen', 'On') %}{% endif %}", PAIR),
        ("{{ not is_state('light.kitchen', 'On') }}", PAIR),
        # The test form, which is what Home Assistant offers besides the call.
        ("{{ 'light.kitchen' is is_state('On') }}", PAIR),
        ("{{ 'light.kitchen' is not is_state('On') }}", PAIR),
        # A list of states, which core's `is_state` takes as well.
        ("{{ is_state('light.kitchen', ['On', 'Dimmed']) }}", ON_AND_DIMMED),
        ("{{ is_state('light.kitchen', ['On',]) }}", PAIR),
        ("{{ 'light.kitchen' is is_state(['On', 'Dimmed']) }}", ON_AND_DIMMED),
        ("{{ 'light.kitchen' is not is_state(['On']) }}", PAIR),
        # Worked out while running, or more than one literal.
        ("{{ is_state(which, 'On') }}", set()),
        ("{{ is_state('light.kitchen', which) }}", set()),
        ("{{ is_state('light.kitchen', 'O' ~ 'n') }}", set()),
        ("{{ is_state('light.kitchen', ['On', which]) }}", set()),
        ("{{ is_state('light.kitchen', ['O' ~ 'n']) }}", set()),
        ("{{ is_state('light.kitchen', []) }}", set()),
        # Core only looks inside a list, so a tuple never matches.
        ("{{ is_state('light.kitchen', ('On', 'Dimmed')) }}", set()),
        ("{{ 'light.kitchen' is is_state(('On', 'Dimmed')) }}", set()),
        # Something binding tighter takes part of the list.
        ("{{ is_state('light.kitchen', ['On'] + more) }}", set()),
        ("{{ is_state('light.kitchen', ['On', 'Dimmed'][0]) }}", set()),
        ("{{ is_state('light.kitchen', ['On'] | reverse) }}", set()),
        ("{{ is_state('light.kitchen', ['On'].copy()) }}", set()),
        ("{{ 'light.kitchen' is is_state(['On'] + more) }}", set()),
        ("{{ 'light.kitchen' is is_state ['On'] }}", set()),
        ("{{ -'light.kitchen' is is_state(['On']) }}", set()),
        ("{{ 'light.' 'light.kitchen' is is_state('On') }}", set()),
        ("{{ 'light.kitchen' is is_state 'On' }}", set()),
        ("{{ 'light.kitchen' is is_state('O' ~ 'n') }}", set()),
        ("{{ ('light.' ~ room) is is_state('On') }}", set()),
        # A test binds to the literal only, also after `~`.
        ("{{ prefix ~ 'light.kitchen' is is_state('On') }}", PAIR),
        # A sign before it makes the test about the signed value.
        ("{{ -'light.kitchen' is is_state('On') }}", set()),
        ("{{ +'light.kitchen' is is_state('On') }}", set()),
        # Not a lookup of Home Assistant's.
        ("{# is_state('light.kitchen', 'On') #}{{ 1 }}", set()),
        ("is_state('light.kitchen', 'On')", set()),
        (
            (
                "{% macro is_state(a, b) %}{% endmacro %}"
                "{{ is_state('light.kitchen', 'On') }}"
            ),
            set(),
        ),
        (
            (
                "{% set is_state = mine %}"
                "{{ is_state('light.kitchen', ['On', 'Dimmed']) }}"
            ),
            set(),
        ),
        ("{{ is_state_attr('light.kitchen', 'mode', 'On') }}", set()),
    ],
)
def test_state_pairs_in_templates(
    template: str, expected: set[tuple[str, str]]
) -> None:
    """Test only literal `is_state` pairs are read from a template."""
    assert extract_state_pairs_from_template(template) == expected


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{ states('light.kitchen') == 'On' }}", PAIR),
        ("{{ states('light.kitchen') != 'On' }}", PAIR),
        ("{{ 'On' == states('light.kitchen') }}", PAIR),
        ("{{ 'On' != states('light.kitchen') }}", PAIR),
        ("{{ states.light.kitchen.state == 'On' }}", PAIR),
        ("{{ 'On' != states.light.kitchen.state }}", PAIR),
        ("{{ states('light.kitchen') in ['On', 'Dimmed'] }}", ON_AND_DIMMED),
        ("{{ states('light.kitchen') not in ('On', 'Dimmed',) }}", ON_AND_DIMMED),
        ("{{ states.light.kitchen.state in ('On',) }}", PAIR),
        # Around it: what is looser than a comparison, or opens and closes.
        ("{% if states('light.kitchen') == 'On' %}{% endif %}", PAIR),
        ("{% if x %}{% elif states('light.kitchen') == 'On' %}{% endif %}", PAIR),
        ("{% set on = states('light.kitchen') == 'On' %}", PAIR),
        ("{{ not states('light.kitchen') == 'On' }}", PAIR),
        ("{{ a and states('light.kitchen') == 'On' or b }}", PAIR),
        ("{{ 1 if states('light.kitchen') == 'On' else 2 }}", PAIR),
        ("{{ (states('light.kitchen') == 'On') }}", PAIR),
        ("{{ [states('light.kitchen') == 'On', 1] }}", PAIR),
        ("{{ iif(states('light.kitchen') == 'On', 1, 2) }}", PAIR),
        ("{{ x if 'On' == states('light.kitchen') else y }}", PAIR),
        # A filter, method, subscript or maths takes part of a side.
        ("{{ states('light.kitchen') | lower == 'on' }}", set()),
        ("{{ states('light.kitchen') == 'On' | lower }}", set()),
        ("{{ 'On' | lower == states('light.kitchen') }}", set()),
        ("{{ 'On' == states('light.kitchen') | lower }}", set()),
        ("{{ states('light.kitchen').upper() == 'ON' }}", set()),
        ("{{ states.light.kitchen.state[0] == 'O' }}", set()),
        ("{{ states.light.kitchen.state_with_unit == 'On' }}", set()),
        ("{{ 'pre' ~ states('light.kitchen') == 'preOn' }}", set()),
        ("{{ states('light.kitchen') ~ 'x' == 'Onx' }}", set()),
        ("{{ states('light.kitchen') == 'O' ~ 'n' }}", set()),
        ("{{ 'O' ~ 'On' == states('light.kitchen') }}", set()),
        ("{{ states('light.kitchen') + 'x' == 'Onx' }}", set()),
        ("{{ - states('light.kitchen') == 'On' }}", set()),
        ("{{ states('light.kitchen') == 'On'.upper() }}", set()),
        ("{{ states('light.kitchen') == 'On'[0] }}", set()),
        ("{{ states('light.kitchen') is string == 'On' }}", set()),
        ("{{ x is not states('light.kitchen') == 'On' }}", set()),
        # Chained, or another comparison right next to it.
        ("{{ states('light.kitchen') == 'On' == x }}", set()),
        ("{{ x == 'On' == states('light.kitchen') }}", set()),
        ("{{ 1 < states('light.kitchen') == 'On' }}", set()),
        ("{{ x in states('light.kitchen') == 'On' }}", set()),
        # Not a literal, or not only literals.
        ("{{ states('light.kitchen') == which }}", set()),
        ("{{ states('light.kitchen') in ['On', which] }}", set()),
        ("{{ states('light.kitchen') in ('On') }}", set()),
        ("{{ states('light.kitchen') in 'On Dimmed' }}", set()),
        ("{{ states('light.kitchen') in [] }}", set()),
        ("{{ states('light.kitchen') in ['On' }}", set()),
        ("{{ 'On' in states('light.kitchen') }}", set()),
        ("{{ states('light.kitchen') < 'On' }}", set()),
        # More than the state.
        ("{{ states('light.kitchen', rounded=True) == 'On' }}", set()),
        ("{{ states('light.kitchen', with_unit=True) == 'On' }}", set()),
        ("{{ states(which) == 'On' }}", set()),
        ("{{ states.light.kitchen == 'On' }}", set()),
        ("{{ x.states('light.kitchen') == 'On' }}", set()),
        ("{{ states('light.' ~ room) == 'On' }}", set()),
        # A template with a `states` of its own.
        ("{% set states = {} %}{{ states('light.kitchen') == 'On' }}", set()),
        (
            (
                "{% macro states(x) %}{% endmacro %}"
                "{{ states.light.kitchen.state == 'On' }}"
            ),
            set(),
        ),
    ],
)
def test_state_comparisons_in_templates(
    template: str, expected: set[tuple[str, str]]
) -> None:
    """Test a state compared to literals is read only when nothing else takes part."""
    assert extract_state_pairs_from_template(template) == expected


def test_own_is_state_leaves_comparisons_alone() -> None:
    """Test a template with an `is_state` of its own still has its comparisons.

    And the other way around: one bad name does not hide the other.
    """
    assert (
        extract_state_pairs_from_template(
            "{% macro is_state(a, b) %}{% endmacro %}"
            "{{ is_state('light.kitchen', 'Off') or states('light.kitchen') == 'On' }}"
        )
        == PAIR
    )
    assert (
        extract_state_pairs_from_template(
            "{% set states = {} %}{{ is_state('light.kitchen', 'On') }}"
        )
        == PAIR
    )


@pytest.mark.parametrize(
    "config",
    [
        *shadowing_configs("states", "{{ states.light.kitchen.state == 'On' }}"),
        *shadowing_configs("states", "{{ states('light.kitchen') == 'On' }}"),
        *shadowing_configs("is_state", "{{ is_state('light.kitchen', 'On') }}"),
    ],
)
def test_names_the_configuration_gives_are_no_lookups(config: dict[str, Any]) -> None:
    """Test a template is not read for a name its configuration took over."""
    assert not extract_state_references_from_config(config).pairs


def test_other_names_leave_lookups_alone() -> None:
    """Test a variable by any other name does not stop a lookup being read."""
    config = {
        "variables": {"level": 1},
        "actions": [
            {"variables": {"mode": "x"}},
            {"wait_template": "{{ states('light.kitchen') == 'On' }}"},
        ],
    }

    assert extract_state_references_from_config(config).pairs == PAIR


def test_what_an_action_is_handed_names_nothing_here() -> None:
    """Test variables handed to a called script are that script's, not ours.

    A variable with a name of its own inside a variables block is not one
    either: only the block's own keys are names.
    """
    config = {
        "variables": {"level": {"states": 1}},
        "actions": [
            {
                "action": "script.turn_on",
                "target": {"entity_id": "script.other"},
                "data": {"variables": {"states": {}}},
            },
            {"event": "spooky", "event_data": {"response_variable": "states"}},
            {"wait_template": "{{ states('light.kitchen') == 'On' }}"},
        ],
    }

    assert extract_state_references_from_config(config).pairs == PAIR
