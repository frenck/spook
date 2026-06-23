"""Tests for the Spook config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.spook.const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


pytestmark = pytest.mark.usefixtures("skip_dependency_setup")


async def test_config_flow_shows_initial_form(hass: HomeAssistant) -> None:
    """Test the config flow shows the initial form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None


async def test_config_flow_can_create_entry_with_restart_later(
    hass: HomeAssistant,
) -> None:
    """Test the config flow can create an entry using restart later."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "choice_restart"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "restart_later"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Your homie"
    assert result["data"] == {}


async def test_config_flow_restart_now_sets_setup_restart_flag(
    hass: HomeAssistant,
) -> None:
    """Test restart now stores the setup restart flag."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "restart_now"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.data[DOMAIN] == "Boo!"


async def test_config_flow_aborts_when_spook_is_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test the config flow aborts when Spook already has an entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_spooked"


async def test_config_flow_can_enable_existing_disabled_entry(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the config flow can enable an existing disabled Spook entry."""
    entry = MockConfigEntry(
        disabled_by=config_entries.ConfigEntryDisabler.USER,
        domain=DOMAIN,
        title="Your homie",
        data={},
    )
    entry.add_to_hass(hass)
    async_set_disabled_by = AsyncMock(return_value=True)
    monkeypatch.setattr(
        hass.config_entries,
        "async_set_disabled_by",
        async_set_disabled_by,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "already_configured"
    assert result["menu_options"] == ["enable_existing"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "enable_existing"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "enabled_existing"
    async_set_disabled_by.assert_awaited_once_with(entry.entry_id, disabled_by=None)


async def test_config_flow_enable_existing_disabled_entry_can_fail(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the config flow aborts when enabling an existing entry fails."""
    entry = MockConfigEntry(
        disabled_by=config_entries.ConfigEntryDisabler.USER,
        domain=DOMAIN,
        title="Your homie",
        data={},
    )
    entry.add_to_hass(hass)
    async_set_disabled_by = AsyncMock(return_value=False)
    monkeypatch.setattr(
        hass.config_entries,
        "async_set_disabled_by",
        async_set_disabled_by,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "enable_existing"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "enable_failed"
    async_set_disabled_by.assert_awaited_once_with(entry.entry_id, disabled_by=None)


async def test_config_flow_aborts_when_enabled_and_disabled_entries_exist(
    hass: HomeAssistant,
) -> None:
    """Test enabled entries take precedence over disabled ones."""
    MockConfigEntry(domain=DOMAIN, title="Your homie", data={}).add_to_hass(hass)
    MockConfigEntry(
        disabled_by=config_entries.ConfigEntryDisabler.USER,
        domain=DOMAIN,
        title="Your homie",
        data={},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_spooked"
