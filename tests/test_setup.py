"""Tests for the Spook config entry setup."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components import spook
from custom_components.spook.const import DOMAIN


pytestmark = pytest.mark.usefixtures("skip_dependency_setup")


class _NoopSpookServiceManager:
    """No-op service manager for setup lifecycle tests."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the no-op service manager."""
        self.hass = hass

    async def async_setup(self) -> None:
        """Set up no services."""

    def async_on_unload(self) -> None:
        """Unload no services."""


class _NoopSpookRepairManager:
    """No-op repair manager for setup lifecycle tests."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the no-op repair manager."""
        self.hass = hass

    async def async_setup(self) -> None:
        """Set up no repairs."""

    async def async_on_unload(self) -> None:
        """Unload no repairs."""


def _link_sub_integrations_noop(_hass: HomeAssistant) -> bool:
    """Skip sub-integration symlink creation during lifecycle tests."""
    return False


async def test_setup_entry_loads_and_unloads(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Spook can be loaded and unloaded as a config entry."""

    async def async_forward_no_platforms(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
    ) -> None:
        """Forward no ectoplasm setup during the lifecycle smoke test."""

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", _link_sub_integrations_noop)
    monkeypatch.setattr(spook, "async_forward_setup_entry", async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _NoopSpookServiceManager)
    monkeypatch.setattr(spook, "SpookRepairManager", _NoopSpookRepairManager)

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
