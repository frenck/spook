"""Tests for entity filtering helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import config_validation as cv

from custom_components.spook.entity_filtering import (
    async_filter_known_services,
    async_find_services_in_sequence,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


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


async def test_templated_action_names_are_not_reported_unknown(
    hass: HomeAssistant,
) -> None:
    """Test templated action names never surface as unknown services.

    The service reference repairs walk validated script configs, where
    ``cv.SERVICE_SCHEMA`` turns a templated action name into a ``Template``
    object. The known-services filter drops non-string values, so templated
    names must never be reported as unknown.

    Note for future raw-config walkers: in raw (unvalidated) configs a
    templated action name is a plain string and needs an explicit
    ``is_template_string`` skip instead.
    """
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"action": "{{ 'notify.' ~ who }}"},
            {"service": "{{ 'light.turn_' ~ toggle_state }}"},
            {"action": "notify.ghost"},
        ]
    )

    found = async_find_services_in_sequence(sequence)

    assert async_filter_known_services(hass, services=found) == {"notify.ghost"}
