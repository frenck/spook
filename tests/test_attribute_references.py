"""Tests for finding the attributes a configuration names."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.spook.reference_extraction import (
    extract_attribute_references_from_config,
)
from custom_components.spook.template_extraction import (
    extract_attribute_pairs_from_template,
)


def _state(**extra: Any) -> dict[str, Any]:
    """Return a state condition on the kitchen light's brightness."""
    return {
        "condition": "state",
        "entity_id": "light.kitchen",
        "attribute": "brightness",
        "state": "255",
        **extra,
    }


PAIR = {("light.kitchen", "brightness")}


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(
            {
                "triggers": [
                    {
                        "trigger": "state",
                        "entity_id": "light.kitchen",
                        "attribute": "brightness",
                    }
                ]
            },
            id="state trigger",
        ),
        pytest.param(
            {
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": "light.kitchen",
                        "attribute": "brightness",
                    }
                ]
            },
            id="legacy state trigger",
        ),
        pytest.param(
            {
                "triggers": [
                    {
                        "trigger": "numeric_state",
                        "entity_id": "light.kitchen",
                        "attribute": "brightness",
                        "above": 10,
                    }
                ]
            },
            id="numeric state trigger",
        ),
        pytest.param({"conditions": [_state()]}, id="state condition"),
        pytest.param(
            {"conditions": [{"condition": "and", "conditions": [_state()]}]},
            id="and",
        ),
        pytest.param(
            {
                "conditions": [
                    {
                        "condition": "or",
                        "conditions": [
                            {"condition": "not", "conditions": [_state()]},
                        ],
                    }
                ]
            },
            id="or and not",
        ),
        pytest.param(
            {
                "actions": [
                    {
                        "choose": [
                            {"conditions": [_state()], "sequence": []},
                        ]
                    }
                ]
            },
            id="choose",
        ),
        pytest.param(
            {"actions": [{"if": [_state()], "then": []}]},
            id="if",
        ),
        pytest.param(
            {"actions": [{"repeat": {"while": [_state()], "sequence": []}}]},
            id="repeat while",
        ),
        pytest.param(
            {"actions": [{"repeat": {"count": 2, "sequence": [_state()]}}]},
            id="repeat sequence",
        ),
        pytest.param(
            {"actions": [{"sequence": [_state()]}]},
            id="sequence",
        ),
        pytest.param({"sequence": [_state()]}, id="script condition step"),
        pytest.param(
            {
                "sequence": [
                    {
                        "wait_for_trigger": [
                            {
                                "trigger": "state",
                                "entity_id": "light.kitchen",
                                "attribute": "brightness",
                            }
                        ]
                    }
                ]
            },
            id="wait for trigger",
        ),
        pytest.param(
            {
                "actions": [
                    {
                        "action": "notify.notify",
                        "data": {
                            "message": "{{ state_attr('light.kitchen', 'brightness') }}"
                        },
                    }
                ]
            },
            id="template in action data",
        ),
        pytest.param(
            {
                "conditions": [
                    {
                        "condition": "template",
                        "value_template": (
                            "{{ is_state_attr('light.kitchen', 'brightness', 255) }}"
                        ),
                    }
                ]
            },
            id="template condition",
        ),
    ],
)
def test_attribute_references_are_found(config: dict[str, Any]) -> None:
    """Test every place an attribute can be named is read."""
    assert extract_attribute_references_from_config(config).pairs == PAIR


def test_every_entity_of_a_list_is_a_pair() -> None:
    """Test a trigger watching several entities names the attribute of each."""
    config = {
        "triggers": [
            {
                "trigger": "state",
                "entity_id": ["light.kitchen", "light.hall"],
                "attribute": "brightness",
            },
            {
                "trigger": "state",
                "entity_id": "light.attic, light.cellar",
                "attribute": "brightness",
            },
        ]
    }

    assert extract_attribute_references_from_config(config).pairs == {
        ("light.kitchen", "brightness"),
        ("light.hall", "brightness"),
        ("light.attic", "brightness"),
        ("light.cellar", "brightness"),
    }


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"conditions": [_state(enabled=False)]}, id="disabled condition"),
        pytest.param(
            {"actions": [{"if": [_state()], "then": [], "enabled": False}]},
            id="disabled step",
        ),
        pytest.param(
            {
                "actions": [
                    {
                        "action": "script.turn_on",
                        "data": {"variables": {"check": _state()}},
                    }
                ]
            },
            id="payload, not a condition",
        ),
        pytest.param(
            {"conditions": [_state(attribute="{{ which }}")]},
            id="templated attribute",
        ),
        pytest.param(
            {"conditions": [_state(entity_id="{{ which }}")]},
            id="templated entity",
        ),
        pytest.param(
            {"conditions": [{"condition": "state", "entity_id": "light.kitchen"}]},
            id="no attribute",
        ),
        pytest.param(
            {
                "triggers": [
                    {
                        "trigger": "event",
                        "event_type": "x",
                        "event_data": {
                            "condition": "state",
                            "entity_id": "light.kitchen",
                            "attribute": "brightness",
                        },
                    }
                ]
            },
            id="event data",
        ),
        pytest.param(
            {
                "alias": "{{ state_attr('light.kitchen', 'Brightness') }}",
                "description": "Uses {{ state_attr('light.kitchen', 'Brightness') }}",
                "actions": [
                    {
                        "alias": "{{ state_attr('light.kitchen', 'Brightness') }}",
                        "delay": 1,
                    }
                ],
            },
            id="names and descriptions",
        ),
        pytest.param(
            {
                "fields": {
                    "level": {
                        "example": "{{ state_attr('light.kitchen', 'Brightness') }}"
                    }
                },
                "sequence": [],
            },
            id="script fields",
        ),
    ],
)
def test_attribute_references_left_alone(config: dict[str, Any]) -> None:
    """Test what is not an attribute reference, or does not run, is left out."""
    references = extract_attribute_references_from_config(config)
    assert not references.pairs
    assert not references.followed


def test_payloads_named_like_metadata_are_still_read() -> None:
    """Test a payload keeps a key that would be metadata elsewhere.

    A calendar event has a `description`, and an action's data is rendered,
    so the template in it is a lookup like any other.
    """
    references = extract_attribute_references_from_config(
        {
            "description": "Not rendered",
            "actions": [
                {
                    "action": "calendar.create_event",
                    "data": {
                        "description": (
                            "{{ state_attr('light.kitchen', 'brightness') }}"
                        )
                    },
                },
                {
                    "variables": {
                        "alias": "{{ state_attr('light.hall', 'brightness') }}"
                    }
                },
            ],
        }
    )

    assert references.pairs == {
        ("light.kitchen", "brightness"),
        ("light.hall", "brightness"),
    }


def test_spook_state_trigger_is_handed_back_whole() -> None:
    """Test Spook's own trigger comes back as it is, with what it follows.

    Which entities it watches depends on the house, and its own filters, so
    that is resolved later the way the trigger does it. One following an
    attribute that is worked out at runtime is not handed back at all.
    """
    followed = {
        "trigger": "spook.state_changed",
        "options": {"domain": ["light"], "attribute": "brightness"},
    }
    templated = {
        "trigger": "spook.state_changed",
        "options": {"domain": ["light"], "attribute": "{{ which }}"},
    }

    references = extract_attribute_references_from_config(
        {"triggers": [followed, templated]}
    )

    assert references.followed == ((followed, "brightness"),)
    assert not references.pairs


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{ state_attr('light.kitchen', 'brightness') }}", PAIR),
        ('{{ state_attr("light.kitchen","brightness") }}', PAIR),
        ("{{ is_state_attr('light.kitchen', 'brightness', 255) }}", PAIR),
        ("{{ 'light.kitchen' | state_attr('brightness') }}", PAIR),
        ("{{ states.light.kitchen.attributes.brightness }}", PAIR),
        ("{{ states.light.kitchen.attributes['brightness'] }}", PAIR),
        ("{{ states.light.kitchen.attributes.get('brightness', 0) }}", PAIR),
        (
            "{{ state_attr('light.kitchen', 'Color Temp') }}",
            {("light.kitchen", "Color Temp")},
        ),
        # Worked out while running: nothing to check.
        ("{{ state_attr(which, 'brightness') }}", set()),
        ("{{ state_attr('light.kitchen', which) }}", set()),
        ("{{ state_attr('light.' ~ room, 'brightness') }}", set()),
        # A method on the attributes is not an attribute.
        ("{{ states.light.kitchen.attributes.items() | list }}", set()),
        # Commented out.
        ("{# state_attr('light.kitchen', 'brightness') #}{{ 1 }}", set()),
        # Not a template at all, or outside of the expressions.
        ("state_attr('light.kitchen', 'brightness')", set()),
        ("state_attr('light.kitchen', 'brightness') {{ 1 }}", set()),
        # Inside a block works as well as inside a variable.
        ("{% if is_state_attr('light.kitchen', 'brightness', 1) %}{% endif %}", PAIR),
        # Built from pieces is not one literal.
        ("{{ state_attr('light.kitchen', 'color_' ~ 'temp_kelvin') }}", set()),
        ("{{ states.light.kitchen.attributes.get('color_' ~ 'temp') }}", set()),
        ("{{ states.light.kitchen.attributes['color_' ~ 'temp'] }}", set()),
        # A method on the attributes, not called, is still the method.
        (
            (
                "{% set getter = states.light.kitchen.attributes.get %}"
                "{{ getter('brightness') }}"
            ),
            set(),
        ),
        ("{{ states.light.kitchen.attributes.items | list }}", set()),
        # A template that gives `states` or `state_attr` a meaning of its own.
        (
            (
                "{% macro state_attr(a, b) %}{{ a }}{% endmacro %}"
                "{{ state_attr('light.kitchen', 'brightness') }}"
            ),
            set(),
        ),
        (
            (
                "{% set states = {'light': 1} %}"
                "{{ states.light.kitchen.attributes.brightness }}"
            ),
            set(),
        ),
        (
            "{% set a, states = 1, 2 %}{{ states.light.kitchen.attributes.brightness }}",
            set(),
        ),
        (
            (
                "{% for states in items %}"
                "{{ states.light.kitchen.attributes.brightness }}{% endfor %}"
            ),
            set(),
        ),
        (
            (
                "{% from 'spooky.jinja' import state_attr %}"
                "{{ state_attr('light.kitchen', 'brightness') }}"
            ),
            set(),
        ),
        # Using them in a statement is not defining them.
        ("{% set level = state_attr('light.kitchen', 'brightness') %}", PAIR),
        (
            (
                "{% for light in states.light %}"
                "{{ state_attr('light.kitchen', 'brightness') }}{% endfor %}"
            ),
            PAIR,
        ),
        (
            (
                "{% macro level(of=state_attr('light.kitchen', 'brightness')) %}"
                "{% endmacro %}"
            ),
            PAIR,
        ),
    ],
)
def test_attribute_pairs_in_templates(
    template: str, expected: set[tuple[str, str]]
) -> None:
    """Test only literal pairs are read from a template."""
    assert extract_attribute_pairs_from_template(template) == expected
