"""Tests for trigger and condition platform key validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.trigger import TRIGGERS

from custom_components.spook.platform_validation import (
    async_filter_unknown_condition_keys,
    async_filter_unknown_trigger_keys,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_builtin_and_alias_keys_are_known(hass: HomeAssistant) -> None:
    """Test built-in trigger and condition keys never report unknown."""
    assert (
        await async_filter_unknown_trigger_keys(
            hass,
            {"state", "event", "time", "time_pattern", "numeric_state", "device"},
        )
        == set()
    )
    assert (
        await async_filter_unknown_condition_keys(
            hass,
            {"and", "or", "not", "state", "template", "time", "trigger", "device"},
        )
        == set()
    )


async def test_unknown_integration_is_reported(hass: HomeAssistant) -> None:
    """Test keys from nonexistent integrations are reported."""
    assert await async_filter_unknown_trigger_keys(
        hass,
        {"ghost_integration.appeared", "state"},
    ) == {"ghost_integration.appeared"}


async def test_integration_without_triggers_is_reported(hass: HomeAssistant) -> None:
    """Test keys from integrations without a trigger platform are reported.

    Spook itself exists as an integration but ships no trigger platform.
    """
    assert await async_filter_unknown_trigger_keys(hass, {"spook.boo"}) == {
        "spook.boo",
    }


async def test_registered_platform_keys_are_known(hass: HomeAssistant) -> None:
    """Test registered trigger keys and domains never report unknown."""
    hass.data[TRIGGERS] = {"ghost_integration.appeared": "ghost_integration"}

    assert (
        await async_filter_unknown_trigger_keys(
            hass,
            # The second key is unregistered, but its domain has a
            # registered platform; key-level validation is Home
            # Assistant's job.
            {"ghost_integration.appeared", "ghost_integration.vanished"},
        )
        == set()
    )


async def test_existing_unloaded_integration_is_not_reported(
    hass: HomeAssistant,
) -> None:
    """Test integrations with trigger support are trusted when not loaded."""
    assert (
        await async_filter_unknown_trigger_keys(hass, {"sun", "template", "mqtt"})
        == set()
    )
