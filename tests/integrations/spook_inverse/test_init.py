"""Tests for the Spook inverse integration setup helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.spook.integrations.spook_inverse import (
    MIGRATION_MINOR_VERSION,
    async_get_source_entity_device_id,
    async_remove_entry,
)
from custom_components.spook.integrations.spook_inverse.const import (
    CONF_HIDE_SOURCE,
    DOMAIN,
)

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
) -> None:
    """Test migration removes the helper from the old source device."""
    source_entry = MockConfigEntry(domain="switch", title="Source")
    source_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
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
        options={
            CONF_ENTITY_ID: "switch.source",
            CONF_HIDE_SOURCE: False,
            "inverse_type": Platform.SWITCH,
        },
        version=1,
        minor_version=1,
    )
    migrated_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=migrated_entry.entry_id,
        identifiers={("switch", "source-device")},
    )
    assert (
        migrated_entry.entry_id in device_registry.async_get(device.id).config_entries
    )

    assert await hass.config_entries.async_setup(migrated_entry.entry_id)
    await hass.async_block_till_done()

    assert migrated_entry.minor_version == MIGRATION_MINOR_VERSION
    assert (
        migrated_entry.entry_id
        not in device_registry.async_get(device.id).config_entries
    )


async def test_async_migrate_entry_handles_unresolved_source_entity_id(
    hass: HomeAssistant,
) -> None:
    """Test migration skips device cleanup when the source entity is unresolved."""
    migrated_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inverse",
        options={
            CONF_ENTITY_ID: "switch.missing",
            CONF_HIDE_SOURCE: False,
            "inverse_type": Platform.SWITCH,
        },
        version=1,
        minor_version=1,
    )
    migrated_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(migrated_entry.entry_id)
    await hass.async_block_till_done()

    assert migrated_entry.minor_version == MIGRATION_MINOR_VERSION


async def test_async_remove_entry_unhides_integration_hidden_source(
    hass: HomeAssistant,
) -> None:
    """Test remove entry unhides the source entity."""
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "switch",
        "test",
        "source",
        suggested_object_id="source",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inverse",
        options={
            CONF_ENTITY_ID: "switch.source",
            CONF_HIDE_SOURCE: True,
            "inverse_type": Platform.SWITCH,
        },
    )

    await async_remove_entry(hass, entry)

    assert entity_registry.async_get("switch.source").hidden_by is None


async def test_async_remove_entry_preserves_user_hidden_source(
    hass: HomeAssistant,
) -> None:
    """Test remove entry leaves non-integration hidden source entities alone."""
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "switch",
        "test",
        "source",
        suggested_object_id="source",
        hidden_by=er.RegistryEntryHider.USER,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inverse",
        options={
            CONF_ENTITY_ID: "switch.source",
            CONF_HIDE_SOURCE: True,
            "inverse_type": Platform.SWITCH,
        },
    )

    await async_remove_entry(hass, entry)

    assert (
        entity_registry.async_get("switch.source").hidden_by
        is er.RegistryEntryHider.USER
    )
