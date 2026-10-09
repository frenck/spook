"""Tests for generic dashboard entity reference extraction."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.spook.dashboard_extraction import (
    extract_actions_from_dashboard_node,
    extract_areas_from_dashboard_node,
    extract_entities_from_dashboard_node,
)


def test_full_dashboard_walk() -> None:
    """Test entities are collected from views, badges, cards, and sections."""
    config = {
        "views": [
            {
                "path": "home",
                "badges": [
                    "sensor.bare_badge",
                    {"type": "entity", "entity": "sensor.dict_badge"},
                ],
                "cards": [
                    {"type": "entity", "entity": "light.kitchen"},
                    {
                        "type": "entities",
                        "entities": [
                            "switch.a",
                            {"entity": "switch.b", "name": "B"},
                        ],
                    },
                ],
                "sections": [
                    {"cards": [{"type": "entity", "entity": "climate.hvac"}]},
                ],
            },
        ],
    }

    assert extract_entities_from_dashboard_node(config) == {
        "sensor.bare_badge",
        "sensor.dict_badge",
        "light.kitchen",
        "switch.a",
        "switch.b",
        "climate.hvac",
    }


def test_actions_targets_and_service_data() -> None:
    """Test entity references inside actions are collected."""
    config = {
        "type": "button",
        "entity": "light.button",
        "tap_action": {
            "action": "perform-action",
            "target": {"entity_id": ["light.a", "light.b"]},
        },
        "hold_action": {
            "action": "call-service",
            "service_data": {"entity_id": "switch.hold"},
        },
        "double_tap_action": {
            "action": "perform-action",
            "data": {"entity_id": "fan.double"},
        },
    }

    assert extract_entities_from_dashboard_node(config) == {
        "light.button",
        "light.a",
        "light.b",
        "switch.hold",
        "fan.double",
    }


def test_picture_elements_and_nested_stacks() -> None:
    """Test deeply nested elements and stacked cards are reached."""
    config = {
        "type": "vertical-stack",
        "cards": [
            {
                "type": "picture-elements",
                "camera_image": "camera.front",
                "image_entity": "image.map",
                "elements": [
                    {"type": "state-badge", "entity": "sensor.temp"},
                    {
                        "type": "conditional",
                        "conditions": [{"entity": "binary_sensor.cond"}],
                        "elements": [{"type": "icon", "entity": "light.nested"}],
                    },
                ],
            },
        ],
    }

    assert extract_entities_from_dashboard_node(config) == {
        "camera.front",
        "image.map",
        "sensor.temp",
        "binary_sensor.cond",
        "light.nested",
    }


def test_custom_card_structure_is_covered() -> None:
    """Test references in an unknown card structure are still found.

    A generic walk reaches entity keys the old per-card walker never knew
    about.
    """
    config = {
        "type": "custom:my-fancy-card",
        "header": {"widgets": [{"entity": "sensor.custom_nested"}]},
        "extra": {"deeply": {"nested": {"entity_id": "switch.custom"}}},
    }

    assert extract_entities_from_dashboard_node(config) == {
        "sensor.custom_nested",
        "switch.custom",
    }


def test_markdown_and_area_card_keys() -> None:
    """Test markdown entity_ids and area card exclude_entities are collected."""
    config = {
        "views": [
            {
                "cards": [
                    {
                        "type": "markdown",
                        "entity_ids": ["sensor.md_a", "sensor.md_b"],
                    },
                    {
                        "type": "area",
                        "area": "living_room",
                        "exclude_entities": ["light.excluded"],
                    },
                ],
            },
        ],
    }

    assert extract_entities_from_dashboard_node(config) == {
        "sensor.md_a",
        "sensor.md_b",
        "light.excluded",
    }


def test_comma_separated_values_are_split() -> None:
    """Test comma-separated entity IDs are split into individual references."""
    config = {"entity_id": "light.a, light.b ,light.c"}

    assert extract_entities_from_dashboard_node(config) == {
        "light.a",
        "light.b",
        "light.c",
    }


def test_non_reference_keys_and_sources_are_ignored() -> None:
    """Test unrelated keys and geo location sources are not collected."""
    config = {
        "type": "map",
        "theme": "some-theme",
        "title": "My Map",
        "geo_location_sources": ["all", "nws"],
    }

    assert extract_entities_from_dashboard_node(config) == set()


@pytest.mark.parametrize("node", [None, [], {}, "string", 42, {"entity": 5}])
def test_degenerate_nodes_yield_nothing(node: Any) -> None:
    """Test scalar, empty, and malformed nodes produce no references."""
    assert extract_entities_from_dashboard_node(node) == set()


def test_area_references_from_cards_and_strategy() -> None:
    """Test area references are collected from area cards and strategies."""
    config = {
        "views": [
            {
                "strategy": {
                    "type": "areas",
                    "areas_display": {
                        "hidden": ["attic"],
                        "order": ["kitchen", "hallway"],
                    },
                },
            },
            {
                "cards": [
                    {"type": "area", "area": "living_room"},
                    {
                        "type": "button",
                        "tap_action": {
                            "action": "perform-action",
                            "target": {"area_id": ["garage", "shed"]},
                        },
                    },
                ],
            },
        ],
    }

    assert extract_areas_from_dashboard_node(config) == {
        "attic",
        "kitchen",
        "hallway",
        "living_room",
        "garage",
        "shed",
    }


def test_area_extraction_ignores_unrelated_keys() -> None:
    """Test non-area keys are not collected as area references."""
    config = {"type": "entity", "entity": "sensor.x", "name": "kitchen"}

    assert extract_areas_from_dashboard_node(config) == set()


def test_an_area_on_anything_but_an_area_card_is_a_label() -> None:
    """A custom card is free to call a caption `area`, and one does.

    flex-horseshoe-card prints whatever is under `area` beneath the gauge.
    Only the area card and the area view strategy take `area` as a reference,
    so only a node of that type has one. #1609.
    """
    config = {
        "views": [
            {
                "strategy": {"type": "area", "area": "kitchen"},
            },
            {
                "cards": [
                    {
                        "type": "custom:flex-horseshoe-card",
                        "entities": [
                            {"entity": "sensor.garage_temperature", "area": "Garaj"},
                        ],
                    },
                    {"type": "custom:area-ish-card", "area": "Not an ID"},
                ],
            },
        ],
    }

    assert extract_areas_from_dashboard_node(config) == {"kitchen"}


def test_bubble_card_keys_of_its_own_are_read() -> None:
    """Bubble Card names entities under keys no other card uses.

    A pop-up can open on an entity's state, and a horizontal buttons stack
    numbers its buttons, each with an entity and a motion sensor.
    """
    config = {
        "cards": [
            {
                "type": "custom:bubble-card",
                "card_type": "pop-up",
                "hash": "#kitchen",
                "trigger_entity": "binary_sensor.kitchen_motion",
            },
            {
                "type": "custom:bubble-card",
                "card_type": "horizontal-buttons-stack",
                "1_link": "#kitchen",
                "1_entity": "light.kitchen",
                "1_pir_sensor": "binary_sensor.kitchen_motion_2",
                "12_entity": "light.attic",
                "2_name": "light.not_an_entity_key",
            },
        ],
    }

    assert extract_entities_from_dashboard_node(config) == {
        "binary_sensor.kitchen_motion",
        "binary_sensor.kitchen_motion_2",
        "light.kitchen",
        "light.attic",
    }


def test_bubble_card_paths_that_already_worked_stay_working() -> None:
    """Sub-buttons, in both the old list and the newer groups, are found."""
    config = {
        "cards": [
            {
                "type": "custom:bubble-card",
                "card_type": "button",
                "entity": "light.living_room",
                "sub_button": [{"entity": "sensor.old_style"}],
            },
            {
                "type": "custom:bubble-card",
                "card_type": "button",
                "sub_button": {
                    "main": [{"entity": "sensor.new_style"}],
                    "bottom": [{"entity": "sensor.bottom_row"}],
                },
            },
        ],
    }

    assert extract_entities_from_dashboard_node(config) == {
        "light.living_room",
        "sensor.old_style",
        "sensor.new_style",
        "sensor.bottom_row",
    }


def test_numbered_keys_on_another_card_are_not_bubble_cards() -> None:
    """A key shaped like `1_entity` is only Bubble Card's on Bubble Card."""
    config = {"type": "custom:some-other-card", "1_entity": "light.kitchen"}

    assert extract_entities_from_dashboard_node(config) == set()


def test_the_mushroom_template_card_area_is_an_area() -> None:
    """Its `area` is the card's area, handed to its templates as an ID."""
    config = {
        "cards": [
            {
                "type": "custom:mushroom-template-card",
                "area": "kitchen",
                "primary": "{{ area_name(area) }}",
            },
            # A template is not an area ID, whatever card it is on.
            {"type": "custom:mushroom-template-card", "area": "{{ 'kitchen' }}"},
        ],
    }

    assert extract_areas_from_dashboard_node(config) == {"kitchen"}


@pytest.mark.parametrize("card_type", [[], {"kind": "gauge"}, None, 42])
def test_a_type_that_is_not_a_string_does_not_stop_the_walk(card_type: Any) -> None:
    """The walk goes into any dict, and some configs have a `type` of their own.

    One that is a list or a dict cannot be looked up by name, and used to end
    the whole search for areas with an error.
    """
    config = {
        "cards": [
            {"type": card_type, "area": "garage"},
            {"type": "area", "area": "kitchen"},
        ],
    }

    assert extract_areas_from_dashboard_node(config) == {"kitchen"}


def test_actions_are_read_off_the_action_not_its_key() -> None:
    """Test every tap, hold and custom card action that performs one is read."""
    node = {
        "cards": [
            {
                "type": "button",
                "tap_action": {
                    "action": "perform-action",
                    "perform_action": "script.goodnight",
                },
                "hold_action": {"action": "call-service", "service": "light.toggle"},
            },
            {
                "type": "custom:mushroom-entity-card",
                "icon_tap_action": {
                    "action": "perform-action",
                    "perform_action": "scene.turn_on",
                },
            },
            {"type": "tile", "tap_action": {"action": "more-info"}},
        ],
    }

    assert extract_actions_from_dashboard_node(node) == {
        "script.goodnight",
        "light.toggle",
        "scene.turn_on",
    }


def test_an_action_is_named_like_the_frontend_reads_it() -> None:
    """Test `perform_action` wins, and `service` is read when it is missing.

    The frontend runs `perform_action || service` for both kinds, so a
    `call-service` written with the new key performs that one.
    """
    node = [
        {
            "action": "perform-action",
            "perform_action": "script.new",
            "service": "script.old",
        },
        {"action": "call-service", "perform_action": "script.migrated"},
        {"action": "perform-action", "service": "script.legacy_key"},
    ]

    assert extract_actions_from_dashboard_node(node) == {
        "script.new",
        "script.migrated",
        "script.legacy_key",
    }


@pytest.mark.parametrize("empty", [None, "", 0, False])
def test_what_the_frontend_passes_over_falls_back_to_service(empty: Any) -> None:
    """Test `service` is read when `perform_action` is empty to JavaScript."""
    node = {
        "action": "perform-action",
        "perform_action": empty,
        "service": "script.fallback",
    }

    assert extract_actions_from_dashboard_node(node) == {"script.fallback"}


@pytest.mark.parametrize("not_empty", [[], {}, ["script.a_list"]])
def test_what_the_frontend_stops_at_does_not_fall_back(not_empty: Any) -> None:
    """Test an empty list or dict stops the lookup, as it does in JavaScript.

    Python calls those empty, JavaScript does not: the frontend takes them,
    fails to perform them, and never gets to `service`.
    """
    node = {
        "action": "perform-action",
        "perform_action": not_empty,
        "service": "script.never_reached",
    }

    assert extract_actions_from_dashboard_node(node) == set()


@pytest.mark.parametrize(
    "name",
    [
        "",
        None,
        "[[[ return 'script.' + entity.state ]]]",
        "{{ 'script.' ~ states('input_select.mode') }}",
        "not_an_action",
        ["script.a_list"],
    ],
)
def test_what_is_not_an_action_name_is_left_alone(name: Any) -> None:
    """Test templates, half-filled editors and other shapes are not names."""
    node = {"action": "perform-action", "perform_action": name}

    assert extract_actions_from_dashboard_node(node) == set()


def test_an_action_key_on_something_else_is_not_an_action() -> None:
    """Test `service` only counts on an action that performs one."""
    node = {"type": "custom:some-card", "service": "script.not_performed"}

    assert extract_actions_from_dashboard_node(node) == set()


def test_actions_a_card_runs_itself_are_not_looked_up() -> None:
    """Test ha-floorplan's own actions are left to the card. #1843."""
    node = {
        "type": "custom:floorplan-card",
        "config": {
            "rules": [
                {
                    "entity": "sensor.clockface",
                    "state_action": [
                        {
                            "action": "call-service",
                            "service": "floorplan.style_set",
                            "service_data": {"element": "hour", "style": "..."},
                        },
                        {
                            "action": "call-service",
                            "service": "light.turn_on",
                            "service_data": {"entity_id": "light.hallway"},
                        },
                    ],
                }
            ]
        },
    }

    assert extract_actions_from_dashboard_node(node) == {"light.turn_on"}


@pytest.mark.parametrize("action_type", [["perform-action"], {"type": "x"}])
def test_an_action_that_is_not_a_string_does_not_stop_the_walk(
    action_type: Any,
) -> None:
    """Test an odd `action` is passed over, and the walk carries on."""
    node = [
        {"action": action_type, "perform_action": "script.odd"},
        {"action": "perform-action", "perform_action": "script.after"},
    ]

    assert extract_actions_from_dashboard_node(node) == {"script.after"}
