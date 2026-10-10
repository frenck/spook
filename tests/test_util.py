"""Tests for Spook utility helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from custom_components.spook import entity_filtering, template_extraction
from custom_components.spook.entity_filtering import (
    KNOWN_TIME_DATE_ENTITY_IDS,
    async_get_all_entity_ids,
    split_comma_separated_entity_ids,
)
from custom_components.spook.template_extraction import (
    async_extract_entities_from_config,
    async_filter_known_entity_ids_with_templates,
    extract_entities_from_template_regex,
    extract_template_strings_from_config,
    is_template_string,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        floor_registry as fr,
        label_registry as lr,
    )


@pytest.mark.parametrize(
    "value",
    [
        "{{ states('light.kitchen') }}",
        "{% if true %}on{% endif %}",
        "prefix {{ x }} suffix",
        "{% set x = 1 %}{{ x }}",
        # A comment on its own is still a template, and Home Assistant will
        # take one as a shorthand condition. #1520.
        "{# just a comment #}",
        "{# leading comment #}{{ x }}",
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
        "{# unmatched",
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
        # Glued to more with `+`, or to a literal right next to it.
        ("{{ states('sensor.room' + suffix) }}", set()),
        ("{{ states(prefix + 'sensor.room') }}", set()),
        ("{{ states('sensor.room' '_bedroom') }}", set()),
        # Adding up two lookups is no gluing.
        (
            "{{ states('sensor.a') | float + states('sensor.b') | float }}",
            {"sensor.a", "sensor.b"},
        ),
        ("{{ ['light.a'] + ['light.b'] }}", {"light.a", "light.b"}),
        ("{{ states('unknown_domain.foo') }}", set()),
        ("{{ states('light.') }}", set()),
        ("{{ 'light.turn_on' }}", set()),
        # A state lookup tries the entity ID in lower case too, so a mixed
        # case one names the lower case entity.
        ("{{ states('sensor.Pump_Interval') }}", {"sensor.pump_interval"}),
        ("{{ is_state('Light.Kitchen', 'on') }}", {"light.kitchen"}),
        ("{{ state_attr( 'Sensor.Pump' , 'x') }}", {"sensor.pump"}),
        ("{{ expand('Light.Kitchen') }}", {"light.kitchen"}),
        ("{{ states.sensor.Pump_Interval.state }}", {"sensor.pump_interval"}),
        ("{{ state_translated('Sensor.Pump') }}", {"sensor.pump"}),
        ("{{ has_value('Sensor.Pump') }}", {"sensor.pump"}),
        ("{{ is_state_attr('Light.Kitchen', 'mode', 'x') }}", {"light.kitchen"}),
        ("{{ closest('Sensor.Phone') }}", {"sensor.phone"}),
        # A registry lookup does not, Jinja's own names never ignore case, and
        # mixed case text is just text.
        ("{{ device_id('sensor.Pump_Interval') }}", set()),
        ("{{ distance('Sensor.Phone') }}", set()),
        ("{{ STATES('sensor.Pump') }}", set()),
        ("{{ States.sensor.Pump.state }}", set()),
        ("{{ 'Sensor.Status' }}", set()),
        # Nor a lookup written in a string, or in the text around expressions.
        ("{{ \"states('Sensor.Pump')\" }}", set()),
        ("text states('Sensor.Pump') {{ 1 }}", set()),
        # Nor the argument of a filter or a test, which is not the entity.
        ("{{ 'sensor.source' | state_attr('sensor.Label') }}", {"sensor.source"}),
        ("{{ 'sensor.source' is is_state('Sensor.Ready') }}", {"sensor.source"}),
        # Nor a piece of an argument.
        ("{{ states('sensor.Pump' + '_interval') }}", set()),
        ("{{ states('sensor.Pump' '_interval') }}", set()),
        # Nor a call through something, with or without spaces.
        ("{{ obj . states('Sensor.Absent') }}", set()),
        ("{% raw %}{{ states('Sensor.Example') }}{% endraw %}", set()),
        # Nor a name that only ends in one, or one the template defines.
        ("{{ my_states('Sensor.Pump') }}", set()),
        ("{{ obj.states('Sensor.Pump') }}", set()),
        ("{{ x.states.sensor.Pump.state }}", set()),
        (
            "{% macro states(x) %}{% endmacro %}{{ states('Sensor.Pump') }}",
            set(),
        ),
        # The same lookups as a filter, with the entity in front of it.
        ("{{ 'Sensor.Pump' | states }}", {"sensor.pump"}),
        ("{{ 'Sensor.Pump' | states(rounded=True) }}", {"sensor.pump"}),
        ("{{ 'Sensor.Pump' | state_attr('unit') }}", {"sensor.pump"}),
        ("{{ 'Sensor.Pump' | has_value }}", {"sensor.pump"}),
        ("{{ 'Sensor.Pump' | state_translated }}", {"sensor.pump"}),
        ("{{ 'Group.Pumps' | expand }}", {"group.pumps"}),
        ("{{ ['light.one', 'Light.Two'] | expand }}", {"light.one", "light.two"}),
        ("{{ 'Group.Kids' | closest }}", {"group.kids"}),
        # And as a test, with the entity tested.
        ("{{ 'Sensor.Pump' is has_value }}", {"sensor.pump"}),
        ("{{ 'Sensor.Pump' is is_state('on') }}", {"sensor.pump"}),
        ("{{ 'Sensor.Pump' is not is_state('on') }}", {"sensor.pump"}),
        ("{{ 'Light.Kitchen' is is_state_attr('mode', 'x') }}", {"light.kitchen"}),
        # Not where Home Assistant has no such filter or test.
        ("{{ 'Sensor.Pump' | is_state('on') }}", set()),
        ("{{ 'Sensor.Pump' is states }}", set()),
        ("{{ 'Sensor.Pump' is state_attr('unit') }}", set()),
        # Nor a filter or test by a dotted name, which is another one.
        ("{{ 'Sensor.Pump' | states.x }}", set()),
        ("{{ 'Sensor.Pump' is has_value.x }}", set()),
        # Nor a literal that a sign takes before the filter or test does.
        ("{{ -'Sensor.Pump' | states }}", set()),
        ("{{ -'Sensor.Pump' is has_value }}", set()),
        # Nor a list that is a subscript of what is in front of it.
        ("{{ pumps['Sensor.Pump'] | expand }}", set()),
        # Nor the name of a filter defined by the template, or in another case.
        ("{% set states = 1 %}{{ 'Sensor.Pump' | states }}", set()),
        ("{{ 'Sensor.Pump' | STATES }}", set()),
        # `expand` looks up every argument, and the literals in a list.
        (
            "{{ expand('light.one', 'Switch.Fan') }}",
            {"light.one", "switch.fan"},
        ),
        ("{{ expand(['sensor.Pump']) }}", {"sensor.pump"}),
        (
            "{{ expand(['light.one', 'Light.Two'], 'Switch.Fan',) }}",
            {"light.one", "light.two", "switch.fan"},
        ),
        (
            "{{ 'light.one' | expand('Switch.Fan', ['Light.Two']) }}",
            {"light.one", "light.two", "switch.fan"},
        ),
        # But not a piece of an argument, or a list with more than literals.
        ("{{ expand('light.one', 'Switch.' ~ fan) }}", {"light.one"}),
        (
            "{{ expand('light.one', 'Switch.Fan' | replace('Fan', 'Pump')) }}",
            {"light.one"},
        ),
        ("{{ expand('light.one', pick('x', 'Switch.Fan')) }}", {"light.one"}),
        ("{{ expand([fan, 'Switch.Fan']) }}", set()),
        ("{{ expand(['Switch.Fan'][1:]) }}", set()),
        ("{{ expand({'Switch.Fan': 1}) }}", set()),
        # `closest` looks up its point and its entities, not its coordinates.
        ("{{ closest('Zone.School', 'Group.Kids') }}", {"zone.school", "group.kids"}),
        ("{{ closest('zone.home', ['Group.Kids']) }}", {"zone.home", "group.kids"}),
        ("{{ closest(52, 4, 'Group.Kids') }}", {"group.kids"}),
        ("{{ closest('Sensor.Lat', 'Sensor.Lon', 'group.kids') }}", {"group.kids"}),
        ("{{ closest(['Zone.Home'], 'group.kids') }}", {"group.kids"}),
        ("{{ closest(*point, 'Group.Kids') }}", set()),
        ("{{ closest('Group.Kids', home=True) }}", set()),
        (
            "{{ 'Group.Kids' | closest('Zone.School') }}",
            {"zone.school", "group.kids"},
        ),
        ("{{ 'Group.Kids' | closest('Sensor.Lat', 'Sensor.Lon') }}", {"group.kids"}),
        ("{{ 'Group.Kids' | closest(52, 4, 'Zone.Home') }}", set()),
        ("{{ 'Group.Kids' | closest(*point) }}", set()),
        # `distance` takes a mixed case one for a coordinate, at any position.
        ("{{ distance('zone.home', 'Sensor.Phone') }}", {"zone.home"}),
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


@pytest.mark.parametrize(
    "template",
    [
        "{{ 'sensor.' 'Sensor.Pump' | states }}",
        "{{ 'sensor.' 'Sensor.Pump' is has_value }}",
    ],
)
def test_a_glued_literal_in_front_of_a_lookup_is_not_looked_up(template: str) -> None:
    """Test a literal glued to the one before it is not taken as the entity.

    Jinja joins the two into one string first. The extraction drops a glued
    literal on its own as well, so this asks the lookup reader directly.
    """
    # pylint: disable-next=protected-access
    looked_up = template_extraction._looked_up_in_any_case(template)  # noqa: SLF001

    assert looked_up == frozenset()


async def test_filter_template_entities_ignores_ignored_domains(
    hass: HomeAssistant,
) -> None:
    """Test ignored entity domains do not leak as unknown template entities."""
    unknown = await async_filter_known_entity_ids_with_templates(
        hass,
        {
            "{{ states('group.family') }}",
            "{{ states('device_tracker.phone') }}",
            "persistent_notification.update",
            "{{ states('light.missing') }}",
        },
        known_entity_ids=set(),
    )

    assert unknown == {"light.missing"}


async def test_filter_template_entities_reports_missing_scenes(
    hass: HomeAssistant,
) -> None:
    """Test scenes are checked rather than ignored wholesale.

    Scenes used to sit in the ignored domains because `scene.create` builds
    them at runtime. Those are found by scanning configurations now, so a
    scene nothing creates is a genuinely missing one.
    """
    unknown = await async_filter_known_entity_ids_with_templates(
        hass,
        {"{{ states('scene.goodnight') }}"},
        known_entity_ids=set(),
    )

    assert unknown == {"scene.goodnight"}


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
        template_extraction,
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
    original = template_extraction.async_extract_entities_from_template_string

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
        template_extraction,
        "async_extract_entities_from_template_string",
        async_extract_entities_from_template_string,
    )
    template = "{{ states('sensor.duplicated') }}"

    assert await async_extract_entities_from_config(
        hass,
        {"first": template, "second": {"nested": template}},
    ) == {"sensor.duplicated"}
    assert calls == 1


def _counting_services(
    monkeypatch: pytest.MonkeyPatch,
    services: set[str],
) -> list[int]:
    """Count service lookups, so the cost of filtering is observable."""
    calls = [0]

    def async_get_all_services(_: HomeAssistant) -> set[str]:
        """Return registered services."""
        calls[0] += 1
        return services

    monkeypatch.setattr(
        template_extraction,
        "async_get_all_services",
        async_get_all_services,
    )

    return calls


async def test_filter_plain_entity_ids_does_not_get_services_when_all_known(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a configuration with nothing wrong pays nothing for the check.

    Action names are only subtracted from what survived the entity check, so
    there is nothing to look up when everything is known. That is the case on
    almost every inspection.
    """
    calls = _counting_services(monkeypatch, {"light.turn_on"})

    assert (
        await async_filter_known_entity_ids_with_templates(
            hass,
            {"sensor.known", "light.known"},
            known_entity_ids={"sensor.known", "light.known"},
        )
        == set()
    )
    assert calls[0] == 0


async def test_filter_plain_entity_ids_never_builds_the_service_set(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test findings are checked against the registry, not against a built set.

    Enumerating every action in the instance costs more than the handful of
    lookups actually needed, and this runs once per inspected item.
    """
    calls = _counting_services(monkeypatch, {"light.turn_on"})

    assert await async_filter_known_entity_ids_with_templates(
        hass,
        {"sensor.missing", "light.unknown", "binary_sensor.gone"},
        known_entity_ids=set(),
    ) == {"sensor.missing", "light.unknown", "binary_sensor.gone"}
    assert calls[0] == 0


async def test_time_date_entities_are_known(
    hass: HomeAssistant,
) -> None:
    """Test Home Assistant time/date entities are treated as known."""
    expected_entity_ids = {
        "sensor.time",
        "sensor.date",
        "sensor.date_time",
        "sensor.date_time_utc",
        "sensor.date_time_iso",
        "sensor.time_date",
        "sensor.time_utc",
    }
    known_entity_ids = async_get_all_entity_ids(hass)

    assert expected_entity_ids == KNOWN_TIME_DATE_ENTITY_IDS
    assert (
        await async_filter_known_entity_ids_with_templates(
            hass,
            expected_entity_ids,
            known_entity_ids=known_entity_ids,
        )
        == set()
    )


async def test_async_filter_known_floor_ids_defaults_to_floor_registry(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test floor IDs are filtered against the floor registry by default."""
    floor = floor_registry.async_create("Upstairs")
    label = label_registry.async_create("Basement")

    assert entity_filtering.async_filter_known_floor_ids(
        hass,
        floor_ids={floor.floor_id, label.label_id, "ghost_floor"},
    ) == {label.label_id, "ghost_floor"}


async def test_entity_id_cache_lifecycle(hass: HomeAssistant) -> None:
    """Test the per-instance entity ID cache wiring.

    Setting up invalidation twice returns the same unsubscribe callable,
    a state addition invalidates the cache, and unsubscribing clears it.
    """
    unsub = entity_filtering.async_setup_all_entity_ids_cache_invalidation(hass)
    assert entity_filtering.async_setup_all_entity_ids_cache_invalidation(hass) is unsub

    assert "light.new" not in async_get_all_entity_ids(hass)

    hass.states.async_set("light.new", "on")
    await hass.async_block_till_done()

    assert "light.new" in async_get_all_entity_ids(hass)

    unsub()
    cache = hass.data[entity_filtering.DATA_ALL_ENTITY_IDS_CACHE]
    assert cache.entity_ids is None
    assert cache.unsubscribe is None


def test_template_candidate_extraction_is_cached() -> None:
    """Test repeated extraction of the same template hits the cache.

    Repairs re-inspect the same unchanged templates on every cycle; the
    regex scan must only run once per distinct template string.
    """
    # pylint: disable-next=protected-access
    extract = template_extraction._extract_entity_candidates_from_template  # noqa: SLF001
    extract.cache_clear()

    template = "{{ states('sensor.cached') }}"
    assert extract(template) == frozenset({"sensor.cached"})
    assert extract(template) == frozenset({"sensor.cached"})

    assert extract.cache_info().hits == 1
    assert extract.cache_info().misses == 1
