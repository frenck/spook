"""Tests for Spook utility helpers."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.spook.util import (
    extract_template_strings_from_config,
    is_template_string,
    split_comma_separated_entity_ids,
)


@pytest.mark.parametrize(
    "value",
    [
        "{{ states('light.kitchen') }}",
        "{% if true %}on{% endif %}",
        "prefix {{ x }} suffix",
        "{% set x = 1 %}{{ x }}",
    ],
)
def test_is_template_string_recognizes_jinja(value: str) -> None:
    """Test Jinja delimiters are recognized as templates."""
    assert is_template_string(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "",
        "light.kitchen",
        "{{ unmatched",
        "{% unmatched",
        "{ not jinja }",
    ],
)
def test_is_template_string_rejects_plain_strings(value: str) -> None:
    """Test plain strings are not recognized as templates."""
    assert is_template_string(value) is False


@pytest.mark.parametrize("value", [None, 42, True, ["{{ x }}"], {"a": "{{ x }}"}])
def test_is_template_string_rejects_non_strings(value: Any) -> None:
    """Test non-string values are not recognized as templates."""
    assert is_template_string(value) is False


def test_split_single_entity_id_returns_one_element_list() -> None:
    """Test a bare entity ID round-trips as a single-item list."""
    assert split_comma_separated_entity_ids("light.kitchen") == ["light.kitchen"]


def test_split_comma_separated_entity_ids() -> None:
    """Test comma-separated entity IDs are split into separate entries."""
    assert split_comma_separated_entity_ids("light.kitchen,light.living_room") == [
        "light.kitchen",
        "light.living_room",
    ]


def test_split_strips_whitespace_around_entries() -> None:
    """Test whitespace around comma-separated entries is stripped."""
    assert split_comma_separated_entity_ids(" light.a ,  light.b , light.c ") == [
        "light.a",
        "light.b",
        "light.c",
    ]


def test_split_drops_empty_entries() -> None:
    """Test empty entries between commas are dropped."""
    assert split_comma_separated_entity_ids("light.a,,light.b, ,light.c") == [
        "light.a",
        "light.b",
        "light.c",
    ]


@pytest.mark.parametrize("value", ["", None, 42, ["light.kitchen"]])
def test_split_empty_or_non_string_returns_empty_list(value: Any) -> None:
    """Test empty strings and non-string values return an empty list."""
    assert split_comma_separated_entity_ids(value) == []


def test_extract_templates_from_plain_string_config() -> None:
    """Test a template string at the top level is collected."""
    assert extract_template_strings_from_config("{{ states('light.kitchen') }}") == [
        "{{ states('light.kitchen') }}",
    ]


def test_extract_templates_ignores_non_template_strings() -> None:
    """Test plain strings are not collected as templates."""
    assert extract_template_strings_from_config("light.kitchen") == []


def test_extract_templates_walks_nested_dict_and_list() -> None:
    """Test template strings in nested dictionaries and lists are collected."""
    config = {
        "alias": "Test",
        "trigger": [
            {"platform": "template", "value_template": "{{ states('sensor.a') }}"},
        ],
        "action": {
            "service": "notify.notify",
            "data": {"message": "{{ states('sensor.b') }}"},
        },
    }

    assert sorted(extract_template_strings_from_config(config)) == [
        "{{ states('sensor.a') }}",
        "{{ states('sensor.b') }}",
    ]


def test_extract_templates_walks_tuples() -> None:
    """Test tuples are walked like lists."""
    assert sorted(
        extract_template_strings_from_config(("{{ a }}", ("nested", "{{ b }}")))
    ) == ["{{ a }}", "{{ b }}"]


@pytest.mark.parametrize("config", [{}, [], None, 42, True])
def test_extract_templates_from_empty_or_scalar_config(config: Any) -> None:
    """Test empty containers and non-string scalars yield no templates."""
    assert extract_template_strings_from_config(config) == []


def test_extract_templates_appends_to_caller_supplied_list() -> None:
    """Test a caller-supplied accumulator is populated in place."""
    sink = ["{{ preexisting }}"]

    result = extract_template_strings_from_config(
        {"value": "{{ added }}"}, strings=sink
    )

    assert result is sink
    assert sink == ["{{ preexisting }}", "{{ added }}"]
