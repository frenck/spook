"""Golden-path tests for Spook's pure utility helpers.

These cover the sync, hass-free helpers in ``custom_components/spook/util.py``
that are reused across ectoplasms — ``is_template_string``,
``split_comma_separated_entity_ids``, and ``extract_template_strings_from_config``.
The async, hass-aware helpers in the same module are intentionally left to
integration tests where a ``HomeAssistant`` instance is available.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from custom_components.spook.util import (
    extract_template_strings_from_config,
    is_template_string,
    split_comma_separated_entity_ids,
)
import pytest

# ---------------------------------------------------------------------------
# is_template_string
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "{{ states('light.kitchen') }}",
        "{% if true %}on{% endif %}",
        "prefix {{ x }} suffix",
        "{% set x = 1 %}{{ x }}",
    ],
)
def test_is_template_string_recognises_jinja(value: str) -> None:
    """Strings containing Jinja delimiters are recognised as templates."""
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
    """Plain strings without matched Jinja delimiters are not templates."""
    assert is_template_string(value) is False


@pytest.mark.parametrize("value", [None, 42, True, ["{{ x }}"], {"a": "{{ x }}"}])
def test_is_template_string_rejects_non_strings(value: object) -> None:
    """Non-string values short-circuit to ``False``."""
    assert is_template_string(value) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# split_comma_separated_entity_ids
# ---------------------------------------------------------------------------


def test_split_single_entity_id_returns_one_element_list() -> None:
    """A bare entity ID round-trips as a single-element list."""
    assert split_comma_separated_entity_ids("light.kitchen") == ["light.kitchen"]


def test_split_comma_separated_entity_ids() -> None:
    """Comma-separated entity IDs are split into individual entries."""
    result = split_comma_separated_entity_ids("light.kitchen,light.living_room")
    assert result == ["light.kitchen", "light.living_room"]


def test_split_strips_whitespace_around_entries() -> None:
    """Whitespace around comma-separated entries is stripped."""
    result = split_comma_separated_entity_ids(" light.a ,  light.b , light.c ")
    assert result == ["light.a", "light.b", "light.c"]


def test_split_drops_empty_entries() -> None:
    """Empty entries between commas are dropped."""
    result = split_comma_separated_entity_ids("light.a,,light.b, ,light.c")
    assert result == ["light.a", "light.b", "light.c"]


@pytest.mark.parametrize("value", ["", None, 42, ["light.kitchen"]])
def test_split_empty_or_non_string_returns_empty_list(value: object) -> None:
    """Empty strings and non-strings short-circuit to ``[]``."""
    assert split_comma_separated_entity_ids(value) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# extract_template_strings_from_config
# ---------------------------------------------------------------------------


def test_extract_templates_from_plain_string_config() -> None:
    """A template string at the top level is collected."""
    assert extract_template_strings_from_config("{{ states('light.kitchen') }}") == [
        "{{ states('light.kitchen') }}",
    ]


def test_extract_templates_ignores_non_template_strings() -> None:
    """Plain strings without Jinja delimiters are not collected."""
    assert extract_template_strings_from_config("light.kitchen") == []


def test_extract_templates_walks_nested_dict_and_list() -> None:
    """Template strings buried in dicts and lists are all collected."""
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
    result = extract_template_strings_from_config(config)
    assert sorted(result) == [
        "{{ states('sensor.a') }}",
        "{{ states('sensor.b') }}",
    ]


def test_extract_templates_walks_tuples() -> None:
    """Tuples are walked just like lists."""
    config = ("{{ a }}", ("nested", "{{ b }}"))
    result = extract_template_strings_from_config(config)
    assert sorted(result) == ["{{ a }}", "{{ b }}"]


def test_extract_templates_from_empty_or_scalar_config() -> None:
    """Empty containers and non-string scalars yield nothing."""
    assert extract_template_strings_from_config({}) == []
    assert extract_template_strings_from_config([]) == []
    assert extract_template_strings_from_config(None) == []
    assert extract_template_strings_from_config(42) == []
    assert extract_template_strings_from_config(True) == []


def test_extract_templates_appends_to_caller_supplied_list() -> None:
    """A caller-supplied accumulator is populated in place."""
    sink: list[str] = ["{{ preexisting }}"]
    result = extract_template_strings_from_config(
        {"value": "{{ added }}"}, strings=sink
    )
    assert result is sink
    assert sink == ["{{ preexisting }}", "{{ added }}"]
