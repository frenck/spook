"""Tests for entity filtering helpers."""

from __future__ import annotations

from custom_components.spook.entity_filtering import async_find_services_in_sequence


def test_find_services_skips_disabled_nested_steps() -> None:
    """Test disabled sequence branches do not report services."""
    sequence = [
        {
            "if": [{"condition": "template", "value_template": "{{ true }}"}],
            "then": [{"action": "notify.disabled_if_service"}],
            "enabled": False,
        },
        {
            "choose": [
                {
                    "conditions": [
                        {"condition": "template", "value_template": "{{ true }}"}
                    ],
                    "sequence": [{"action": "notify.disabled_choose_service"}],
                }
            ],
            "enabled": False,
        },
        {
            "parallel": [
                {"sequence": [{"action": "notify.disabled_parallel_service"}]}
            ],
            "enabled": False,
        },
        {
            "repeat": {
                "count": 1,
                "sequence": [{"action": "notify.disabled_repeat_service"}],
            },
            "enabled": False,
        },
        {"action": "light.turn_on"},
    ]

    assert async_find_services_in_sequence(sequence) == {"light.turn_on"}


def test_find_services_keeps_enabled_none_steps() -> None:
    """Test only explicitly disabled steps are skipped."""
    sequence = [{"action": "light.turn_on", "enabled": None}]

    assert async_find_services_in_sequence(sequence) == {"light.turn_on"}
