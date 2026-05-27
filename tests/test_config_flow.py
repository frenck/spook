"""Tests for the Spook config flow."""

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.spook.const import DOMAIN


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
