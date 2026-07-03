"""Tests for generic dashboard entity reference extraction."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.spook.dashboard_extraction import (
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
