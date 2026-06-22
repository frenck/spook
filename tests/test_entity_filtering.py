"""Tests for entity filtering helpers."""

from __future__ import annotations

from custom_components.spook.entity_filtering import async_find_services_in_sequence


def test_find_services_skips_disabled_nested_steps() -> None:
    """Test disabled sequence branches do not report services."""
    sequence = [
        {
            "if": "{{ true }}",
            "then": [{"action": "notify.missing_service"}],
            "enabled": False,
        },
        {"action": "light.turn_on"},
    ]

    assert async_find_services_in_sequence(sequence) == {"light.turn_on"}
