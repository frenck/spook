"""Tests for forwarding Spook's platforms to the ectoplasms."""

# pylint: disable=wrong-import-order

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import spook
from custom_components.spook import setup_helpers
from custom_components.spook.const import DOMAIN, PLATFORMS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import CoreState
from homeassistant.helpers import entity_platform, entity_registry as er
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("skip_dependency_setup")

# Long enough for a platform to set up, short enough that one waiting on the
# blocked import thread gives up and says so well before the thread is let go.
PLATFORM_SETUP_TIMEOUT = 5
IMPORT_THREAD_HELD_FOR = 30


def _no_links(_hass: HomeAssistant) -> set[str]:
    """Skip creating the sub integration symlinks."""
    return set()


def _spook_entity_domains(hass: HomeAssistant, entry: ConfigEntry) -> set[str]:
    """Return the domains Spook has registered entities in."""
    return {
        entity.domain
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }


def _platform_timeouts(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the platforms that gave up waiting on their setup."""
    return [
        record.name
        for record in caplog.records
        if "is taking longer than" in record.getMessage()
    ]


async def _async_set_up_spook(hass: HomeAssistant) -> MockConfigEntry:
    """Set Spook up the way a starting Home Assistant does."""
    hass.set_state(CoreState.not_running)
    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    return entry


async def test_platforms_do_not_wait_on_the_import_thread(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test every platform sets up while another integration holds the import thread.

    The import executor has a single thread, and every integration starting up
    queues on it. A platform that put a job on it waited for all of them, and
    the wait counted against its setup timeout. #1898.
    """
    monkeypatch.setattr(spook, "link_sub_integrations", _no_links)
    monkeypatch.setattr(entity_platform, "SLOW_SETUP_MAX_WAIT", PLATFORM_SETUP_TIMEOUT)

    release = threading.Event()
    forward = hass.config_entries.async_forward_entry_setups

    async def _forward_with_the_import_thread_taken(
        entry: ConfigEntry, platforms: Iterable[Platform]
    ) -> None:
        platforms = list(platforms)

        # Whatever Home Assistant imports itself on the way to a platform is
        # loaded first. Only what Spook's platforms do is left to measure.
        integration = await async_get_integration(hass, DOMAIN)
        await integration.async_get_platforms(platforms)
        for platform in platforms:
            assert await async_setup_component(hass, platform, {})

        # Somebody else's slow import, holding the only import thread.
        hass.async_add_import_executor_job(release.wait, IMPORT_THREAD_HELD_FOR)
        await forward(entry, platforms)

    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        _forward_with_the_import_thread_taken,
    )

    caplog.set_level(logging.ERROR)
    try:
        entry = await _async_set_up_spook(hass)
        domains = _spook_entity_domains(hass, entry)
    finally:
        release.set()
    await hass.async_block_till_done()

    assert _platform_timeouts(caplog) == []
    assert {Platform.BUTTON, Platform.EVENT, Platform.SENSOR} <= domains


async def test_platform_modules_are_imported_before_forwarding(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the platforms find their ectoplasm modules already imported."""
    monkeypatch.setattr(spook, "link_sub_integrations", _no_links)

    entry = await _async_set_up_spook(hass)
    await hass.async_block_till_done()

    imported = hass.data[setup_helpers.DATA_ECTOPLASM_PLATFORMS]
    assert set(imported) == set(PLATFORMS)
    assert [module.__name__ for module in imported[Platform.EVENT]] == [
        "custom_components.spook.ectoplasms.repairs.event"
    ]

    # Gone with Spook, so nothing stale is left for a later setup to find.
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert setup_helpers.DATA_ECTOPLASM_PLATFORMS not in hass.data


async def test_a_platform_that_does_not_import_fails_alone(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a module that does not import fails its own platform and no other.

    The same as when each platform imported its own modules: Home Assistant
    logs the error for that platform, and Spook and its other platforms load.
    """
    monkeypatch.setattr(spook, "link_sub_integrations", _no_links)
    import_platform_modules = setup_helpers._import_ectoplasm_platform_modules  # noqa: SLF001  # pylint: disable=protected-access

    def _button_does_not_import(platform: Platform) -> list:
        if platform is Platform.BUTTON:
            msg = "No module named 'a_button_dependency'"
            raise ModuleNotFoundError(msg)
        return import_platform_modules(platform)

    monkeypatch.setattr(
        setup_helpers, "_import_ectoplasm_platform_modules", _button_does_not_import
    )

    entry = await _async_set_up_spook(hass)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    domains = _spook_entity_domains(hass, entry)
    assert Platform.BUTTON not in domains
    assert {Platform.EVENT, Platform.SENSOR} <= domains
    assert "Error while setting up spook platform for button" in caplog.text
    assert "a_button_dependency" in caplog.text
