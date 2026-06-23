"""Tests for Spook utility helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from custom_components.spook import entity_filtering
from custom_components.spook.entity_filtering import (
    KNOWN_TIME_DATE_ENTITY_IDS,
    async_extract_entities_from_config,
    async_filter_known_entity_ids_with_templates,
    async_get_all_entity_ids,
    extract_entities_from_template_regex,
    extract_template_strings_from_config,
    is_template_string,
    split_comma_separated_entity_ids,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


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


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{ states('light.kitchen') }}", {"light.kitchen"}),
        ("{{ state_attr('sensor.energy', 'unit') }}", {"sensor.energy"}),
        ("{{ is_state('switch.fan', 'on') }}", {"switch.fan"}),
        ("{{ is_state_attr('climate.hvac', 'mode', 'heat') }}", {"climate.hvac"}),
        ("{{ has_value('sensor.power') }}", {"sensor.power"}),
        ("{{ state_translated('binary_sensor.motion') }}", {"binary_sensor.motion"}),
        ("{{ device_id('light.kitchen') }}", {"light.kitchen"}),
        ("{{ device_name('switch.fan') }}", {"switch.fan"}),
        ("{{ device_attr('sensor.router', 'name') }}", {"sensor.router"}),
        (
            "{{ is_device_attr('sensor.router', 'manufacturer', 'x') }}",
            {"sensor.router"},
        ),
        ("{{ config_entry_id('sensor.power') }}", {"sensor.power"}),
        ("{{ area_id('sensor.hall') }}", {"sensor.hall"}),
        ("{{ area_name('sensor.hall') }}", {"sensor.hall"}),
        ("{{ floor_id('sensor.upstairs') }}", {"sensor.upstairs"}),
        ("{{ floor_name('sensor.upstairs') }}", {"sensor.upstairs"}),
        ("{{ is_hidden_entity('sensor.hidden') }}", {"sensor.hidden"}),
        ("{{ expand('group.lights') }}", {"group.lights"}),
        ("{{ distance('sensor.home') }}", {"sensor.home"}),
        ("{{ closest('sensor.a') }}", {"sensor.a"}),
        ("{{ states.binary_sensor.door.state }}", {"binary_sensor.door"}),
        (
            "{{ states.sensor.temperature.attributes.unit_of_measurement }}",
            {"sensor.temperature"},
        ),
        ("{{ ['light.a', 'switch.b'] }}", {"light.a", "switch.b"}),
        (
            "{{ expand('light.kitchen', 'switch.fan') }}",
            {"light.kitchen", "switch.fan"},
        ),
        (
            "{{ ['light.kitchen'] | select('is_state', 'on') | list }}",
            {"light.kitchen"},
        ),
        ("{{ 'light.' ~ room }}", set()),
        ("{{ states('unknown_domain.foo') }}", set()),
        ("{{ states('light.') }}", set()),
        ("{{ 'light.turn_on' }}", set()),
    ],
)
def test_extract_entities_from_template_regex(
    hass: HomeAssistant,
    template: str,
    expected: set[str],
) -> None:
    """Test entity IDs are extracted from supported template forms."""
    hass.services.async_register(
        "light",
        "turn_on",
        lambda _: None,
    )

    assert extract_entities_from_template_regex(hass, template) == expected


async def test_filter_template_entities_ignores_ignored_domains(
    hass: HomeAssistant,
) -> None:
    """Test ignored entity domains do not leak as unknown template entities."""
    unknown = await async_filter_known_entity_ids_with_templates(
        hass,
        {
            "{{ states('scene.goodnight') }}",
            "{{ states('group.family') }}",
            "{{ states('device_tracker.phone') }}",
            "persistent_notification.update",
            "{{ states('light.missing') }}",
        },
        known_entity_ids=set(),
    )

    assert unknown == {"light.missing"}


async def test_extract_entities_from_config_reuses_known_services(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test config template extraction reuses service lookup results."""
    calls = 0

    def async_get_all_services(_: HomeAssistant) -> set[str]:
        """Return registered services."""
        nonlocal calls
        calls += 1
        return {"light.turn_on"}

    monkeypatch.setattr(
        entity_filtering,
        "async_get_all_services",
        async_get_all_services,
    )

    config = {
        "first": "{{ states('sensor.one') }} {{ 'light.turn_on' }}",
        "second": "{{ states('sensor.two') }} {{ 'light.turn_on' }}",
    }

    assert await async_extract_entities_from_config(hass, config) == {
        "sensor.one",
        "sensor.two",
    }
    assert calls == 1


async def test_extract_entities_from_config_reuses_duplicate_template_results(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test duplicate template strings are extracted once per config scan."""
    calls = 0
    original = entity_filtering.async_extract_entities_from_template_string

    async def async_extract_entities_from_template_string(
        hass: HomeAssistant,
        template_str: str,
        known_services: set[str] | None = None,
    ) -> set[str]:
        """Extract entity IDs from a template string."""
        nonlocal calls
        calls += 1
        return await original(hass, template_str, known_services)

    monkeypatch.setattr(
        entity_filtering,
        "async_extract_entities_from_template_string",
        async_extract_entities_from_template_string,
    )
    template = "{{ states('sensor.duplicated') }}"

    assert await async_extract_entities_from_config(
        hass,
        {"first": template, "second": {"nested": template}},
    ) == {"sensor.duplicated"}
    assert calls == 1


async def test_filter_plain_entity_ids_does_not_get_services(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test plain entity filtering avoids service lookups."""
    calls = 0

    def async_get_all_services(_: HomeAssistant) -> set[str]:
        """Return registered services."""
        nonlocal calls
        calls += 1
        return {"light.turn_on"}

    monkeypatch.setattr(
        entity_filtering,
        "async_get_all_services",
        async_get_all_services,
    )

    assert await async_filter_known_entity_ids_with_templates(
        hass,
        {"sensor.missing", "light.unknown"},
        known_entity_ids=set(),
    ) == {"sensor.missing", "light.unknown"}
    assert calls == 0


async def test_time_date_entities_are_known(
    hass: HomeAssistant,
) -> None:
    """Test Home Assistant time/date entities are treated as known."""
    known_entity_ids = async_get_all_entity_ids(hass)

    assert (
        await async_filter_known_entity_ids_with_templates(
            hass,
            KNOWN_TIME_DATE_ENTITY_IDS,
            known_entity_ids=known_entity_ids,
        )
        == set()
    )
