"""Tests for the Spook inverse integration setup helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.spook.integrations.spook_inverse import (
    MIGRATION_MINOR_VERSION,
    async_get_source_entity_device_id,
    async_migrate_entry,
)
from custom_components.spook.integrations.spook_inverse.const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_async_get_source_entity_device_id_resolves_entity_id(
    hass: HomeAssistant,
) -> None:
    """Test source device lookup resolves registered entity IDs."""
    config_entry = MockConfigEntry(domain="switch", title="Source")
    config_entry.add_to_hass(hass)

    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("switch", "source-device")},
    )
    er.async_get(hass).async_get_or_create(
        "switch",
        "test",
        "source",
        suggested_object_id="source",
        device_id=device.id,
    )

    assert async_get_source_entity_device_id(hass, "switch.source") == device.id


async def test_async_migrate_entry_removes_helper_from_source_device(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test migration removes the helper from the old source device."""
    source_entry = MockConfigEntry(domain="switch", title="Source")
    source_entry.add_to_hass(hass)

    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source_entry.entry_id,
        identifiers={("switch", "source-device")},
    )
    er.async_get(hass).async_get_or_create(
        "switch",
        "test",
        "source",
        suggested_object_id="source",
        device_id=device.id,
    )

    migrated_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inverse",
        options={CONF_ENTITY_ID: "switch.source"},
        version=1,
        minor_version=1,
    )
    migrated_entry.add_to_hass(hass)

    calls: list[dict[str, Any]] = []

    def remove_helper_from_source_device(
        hass: HomeAssistant,
        *,
        helper_config_entry_id: str,
        source_device_id: str,
    ) -> None:
        """Capture source device cleanup calls."""
        calls.append(
            {
                "hass": hass,
                "helper_config_entry_id": helper_config_entry_id,
                "source_device_id": source_device_id,
            }
        )

    monkeypatch.setattr(
        "custom_components.spook.integrations.spook_inverse."
        "async_remove_helper_config_entry_from_source_device",
        remove_helper_from_source_device,
    )

    assert await async_migrate_entry(hass, migrated_entry)

    assert migrated_entry.minor_version == MIGRATION_MINOR_VERSION
    assert calls == [
        {
            "hass": hass,
            "helper_config_entry_id": migrated_entry.entry_id,
            "source_device_id": device.id,
        }
    ]


async def test_async_migrate_entry_handles_missing_source_entity_id(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test migration skips device cleanup when old options lack an entity ID."""
    migrated_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inverse",
        options={},
        version=1,
        minor_version=1,
    )
    migrated_entry.add_to_hass(hass)

    monkeypatch.setattr(
        "custom_components.spook.integrations.spook_inverse."
        "async_remove_helper_config_entry_from_source_device",
        pytest.fail,
    )

    assert await async_migrate_entry(hass, migrated_entry)

    assert migrated_entry.minor_version == MIGRATION_MINOR_VERSION
