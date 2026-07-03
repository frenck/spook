"""Tests for target reference extraction from raw configurations."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.spook.reference_extraction import extract_targets_from_config


def test_repeat_nested_targets_are_found() -> None:
    """Test targets inside repeat sequences are collected.

    Home Assistant's built-in reference walkers miss ``repeat`` entirely;
    this walker is the compensation.
    """
    config = {
        "actions": [
            {
                "repeat": {
                    "count": 3,
                    "sequence": [
                        {
                            "action": "light.turn_on",
                            "target": {"area_id": "attic"},
                        },
                        {
                            "wait_for_trigger": [
                                {
                                    "trigger": "state",
                                    "entity_id": "binary_sensor.motion",
                                },
                            ],
                            "timeout": 10,
                        },
                    ],
                    "until": [
                        {
                            "condition": "device",
                            "device_id": "abcdef0123456789abcdef0123456789",
                            "domain": "light",
                            "type": "is_on",
                        },
                    ],
                },
            },
        ],
    }

    targets = extract_targets_from_config(config)

    assert targets.area_ids == {"attic"}
    assert targets.device_ids == {"abcdef0123456789abcdef0123456789"}


def test_targets_in_triggers_conditions_and_actions() -> None:
    """Test target blocks are collected from every automation section."""
    config = {
        "triggers": [
            {
                "trigger": "light.turned_on",
                "target": {"floor_id": "upstairs", "label_id": ["security"]},
            },
        ],
        "conditions": [
            {
                "condition": "device",
                "device_id": "1234567890abcdef1234567890abcdef",
                "domain": "light",
                "type": "is_on",
            },
        ],
        "actions": [
            {
                "choose": [
                    {
                        "conditions": [],
                        "sequence": [
                            {
                                "action": "light.turn_off",
                                "target": {
                                    "area_id": ["kitchen", "hallway"],
                                },
                            },
                        ],
                    },
                ],
                "default": [
                    {
                        "action": "light.turn_off",
                        "data": {"area_id": "garage"},
                    },
                ],
            },
        ],
    }

    targets = extract_targets_from_config(config)

    assert targets.area_ids == {"kitchen", "hallway", "garage"}
    assert targets.device_ids == {"1234567890abcdef1234567890abcdef"}
    assert targets.floor_ids == {"upstairs"}
    assert targets.label_ids == {"security"}


def test_event_data_and_variables_are_excluded() -> None:
    """Test payload subtrees are not mistaken for references.

    An ``area_id`` inside ``event_data`` filters incoming events, and
    variables only become references where they are used.
    """
    config = {
        "triggers": [
            {
                "trigger": "event",
                "event_type": "custom_event",
                "event_data": {"device_id": "payload", "area_id": "payload"},
            },
        ],
        "variables": {"area_id": "not_a_reference"},
        "actions": [
            {
                "event": "outgoing_event",
                "event_data_template": {"label_id": "payload"},
            },
        ],
    }

    targets = extract_targets_from_config(config)

    assert targets.area_ids == set()
    assert targets.device_ids == set()
    assert targets.label_ids == set()


@pytest.mark.parametrize(
    "value",
    [
        "{{ my_area }}",
        "all",
        "none",
        "",
        42,
        None,
        {"nested": "dict"},
    ],
)
def test_unresolvable_values_are_skipped(value: Any) -> None:
    """Test templated, constant, and non-string values are not collected."""
    config = {"actions": [{"target": {"area_id": value}}]}

    assert extract_targets_from_config(config).area_ids == set()


def test_mixed_list_keeps_plain_ids_only() -> None:
    """Test lists keep plain IDs while skipping unresolvable entries."""
    config = {
        "target": {"area_id": ["kitchen", "{{ dynamic }}", "none", 5]},
    }

    assert extract_targets_from_config(config).area_ids == {"kitchen"}


@pytest.mark.parametrize("config", [None, [], {}, "just a string", 42])
def test_empty_or_scalar_configs_yield_nothing(config: Any) -> None:
    """Test degenerate configurations produce no references."""
    targets = extract_targets_from_config(config)

    assert not targets.area_ids
    assert not targets.device_ids
    assert not targets.floor_ids
    assert not targets.label_ids
