"""Tests for the Spook inverse config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, Platform
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.spook.integrations.spook_inverse.const import (
    CONF_HIDE_SOURCE,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _create_source_entity(hass: HomeAssistant, domain: str) -> str:
    """Create a source entity and return its entity ID."""
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        domain,
        "test",
        "source",
        suggested_object_id="source",
    )
    return entity_entry.entity_id


@pytest.mark.parametrize("platform", [Platform.BINARY_SENSOR, Platform.SWITCH])
async def test_config_flow_creates_inverse_entry(
    hass: HomeAssistant,
    platform: Platform,
) -> None:
    """Test config flow creates an inverse helper entry."""
    source_entity_id = _create_source_entity(hass, platform)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [Platform.BINARY_SENSOR, Platform.SWITCH]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": platform},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == platform

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Inverse source",
            CONF_ENTITY_ID: source_entity_id,
            CONF_HIDE_SOURCE: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Inverse source"
    assert result["data"] == {}
    assert result["options"] == {
        "inverse_type": platform,
        CONF_NAME: "Inverse source",
        CONF_ENTITY_ID: source_entity_id,
        CONF_HIDE_SOURCE: True,
    }
    assert (
        er.async_get(hass).async_get(source_entity_id).hidden_by
        is er.RegistryEntryHider.INTEGRATION
    )


async def test_options_flow_updates_hide_source_state(
    hass: HomeAssistant,
) -> None:
    """Test options flow hides and unhides the source entity."""
    source_entity_id = _create_source_entity(hass, Platform.SWITCH)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inverse source",
        options={
            "inverse_type": Platform.SWITCH,
            CONF_ENTITY_ID: source_entity_id,
            CONF_HIDE_SOURCE: False,
        },
    )
    entry.add_to_hass(hass)
    own_entity_id = (
        er.async_get(hass)
        .async_get_or_create(
            Platform.SWITCH,
            DOMAIN,
            "inverse_source",
            config_entry=entry,
            suggested_object_id="inverse_source",
        )
        .entity_id
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == Platform.SWITCH
    schema = result["data_schema"].schema
    entity_selector = schema[next(iter(schema))]
    assert entity_selector.config["domain"] == [Platform.SWITCH]
    assert entity_selector.config["exclude_entities"] == [own_entity_id]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ENTITY_ID: source_entity_id,
            CONF_HIDE_SOURCE: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "inverse_type": Platform.SWITCH,
        CONF_ENTITY_ID: source_entity_id,
        CONF_HIDE_SOURCE: True,
    }
    assert (
        er.async_get(hass).async_get(source_entity_id).hidden_by
        is er.RegistryEntryHider.INTEGRATION
    )

    hass.config_entries.async_update_entry(entry, options=result["data"])

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ENTITY_ID: source_entity_id,
            CONF_HIDE_SOURCE: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "inverse_type": Platform.SWITCH,
        CONF_ENTITY_ID: source_entity_id,
        CONF_HIDE_SOURCE: False,
    }
    assert er.async_get(hass).async_get(source_entity_id).hidden_by is None
