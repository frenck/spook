"""Tests for entity filtering helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
)

from custom_components.spook.entity_filtering import (
    async_filter_known_device_ids,
    async_filter_known_services,
    async_find_services_in_sequence,
    async_get_all_device_ids,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    import pytest


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


def test_find_services_stops_at_bare_condition() -> None:
    """Test steps after a bare condition step are not reported."""
    sequence = [
        {"action": "light.turn_on"},
        {"condition": "template", "value_template": "{{ is_state('a.b', 'on') }}"},
        {"action": "zha.issue_zigbee_cluster_command"},
    ]

    assert async_find_services_in_sequence(sequence) == {"light.turn_on"}


def test_find_services_ignores_disabled_bare_condition() -> None:
    """Test a disabled condition step does not gate later steps."""
    sequence = [
        {"condition": "template", "value_template": "{{ false }}", "enabled": False},
        {"action": "light.turn_on"},
    ]

    assert async_find_services_in_sequence(sequence) == {"light.turn_on"}


def test_find_services_condition_gates_only_its_own_sequence() -> None:
    """Test a condition inside a nested sequence does not gate the outer one."""
    sequence = [
        {
            "repeat": {
                "count": 2,
                "sequence": [
                    {"condition": "template", "value_template": "{{ x }}"},
                    {"action": "zha.issue_zigbee_cluster_command"},
                ],
            },
        },
        {"action": "light.turn_on"},
    ]

    assert async_find_services_in_sequence(sequence) == {"light.turn_on"}

    
def test_registered_device_ids_are_known(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test registered devices are known and made-up IDs are not."""
    entry = MockConfigEntry(domain="test", title="Test")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", "device")},
    )

    assert device.id in async_get_all_device_ids(hass)
    assert async_filter_known_device_ids(
        hass,
        device_ids={device.id, "not-a-device"},
    ) == {"not-a-device"}


def test_composite_device_ids_are_known(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test pre-split device IDs are not reported as unknown.

    Home Assistant Core 2026.8 split devices spanning multiple config entries
    into one device per entry. The pre-split ID is gone from the registry, but
    still resolves, so automations targeting it keep working.
    """
    entry = MockConfigEntry(domain="test", title="Test")
    entry.add_to_hass(hass)
    split = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", "split-device")},
    )
    # Stubbed so the test also runs on cores that predate the device split.
    monkeypatch.setattr(
        device_registry.devices,
        "get_composite_splits",
        lambda: {"pre-split-id": [split]},
        raising=False,
    )

    assert "pre-split-id" in async_get_all_device_ids(hass)
    assert async_filter_known_device_ids(hass, device_ids={"pre-split-id"}) == set()
