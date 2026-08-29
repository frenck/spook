"""Tests for the Spook config entry setup."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
import logging

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    RESTART_EXIT_CODE,
)
from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.core import Context, CoreState
from homeassistant.helpers import issue_registry as ir

from custom_components import spook
from custom_components.spook.automation_runs import async_get_automation_runs
from custom_components.spook.const import DOMAIN
from custom_components.spook.run_history import async_get_run_history
from custom_components.spook.snoozing import DATA_SNOOZING
from custom_components.spook.integration_linking import (
    link_sub_integrations,
    unlink_sub_integrations,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


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


class _SnoozeCheckingServiceManager:
    """Service manager that records what was in place before it registered."""

    had_snoozing: bool | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the checking service manager."""
        self.hass = hass

    async def async_setup(self) -> None:
        """Record whether the snooze register was already there."""
        type(self).had_snoozing = DATA_SNOOZING in self.hass.data

    def async_on_unload(self) -> None:
        """Unload no services."""


class _RecordingSpookRepairManager:
    """Repair manager that records whether it was set up."""

    setups = 0

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the recording repair manager."""
        self.hass = hass

    async def async_setup(self) -> None:
        """Record that repairs were set up."""
        type(self).setups += 1

    async def async_on_unload(self) -> None:
        """Unload no repairs."""


def _sub_integration_names() -> set[str]:
    """Return bundled Spook sub-integration names."""
    return {
        manifest.parent.name
        for manifest in (
            Path(__file__).parents[1] / "custom_components" / DOMAIN / "integrations"
        ).rglob("*/manifest.json")
    }


def _create_sub_integration_sources(config_dir: Path) -> None:
    """Create matching config-dir source folders for Spook sub-integrations."""
    for name in _sub_integration_names():
        (config_dir / "custom_components" / DOMAIN / "integrations" / name).mkdir(
            parents=True,
            exist_ok=True,
        )


def _link_sub_integrations_changed(_hass: HomeAssistant) -> bool:
    """Pretend sub-integration symlink creation changed the config dir."""
    return True


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


async def test_setup_entry_starts_and_stops_the_automation_run_register(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the config entry owns the automation run register.

    A condition inside an action sequence is only built once that sequence
    runs, which is after the automation announced itself, so the register has
    to be listening before any of that. Nothing else in the suite proves the
    entry is what starts it: the condition tests all have a register running
    for their own reasons.
    """

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

    assert EVENT_AUTOMATION_TRIGGERED not in hass.bus.async_listeners()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert EVENT_AUTOMATION_TRIGGERED in hass.bus.async_listeners()

    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {"entity_id": "automation.goodnight"},
        context=Context(id="a-run"),
    )
    await hass.async_block_till_done()

    runs = async_get_automation_runs(hass)
    assert runs.async_which("a-run") == "automation.goodnight"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert EVENT_AUTOMATION_TRIGGERED not in hass.bus.async_listeners()
    assert runs.async_which("a-run") is None, "kept remembering after unloading"


async def test_setup_entry_has_the_snooze_register_before_the_actions(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the snooze register is in place before any action can be called.

    `automation.snooze` reaches for it the moment somebody calls it, so
    registering the actions first leaves a window where the action exists and
    the register does not. That window is a real one: an automation set off by
    Home Assistant starting can call it.
    """

    async def async_forward_no_platforms(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
    ) -> None:
        """Forward no ectoplasm setup during the lifecycle smoke test."""

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", _link_sub_integrations_noop)
    monkeypatch.setattr(spook, "async_forward_setup_entry", async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _SnoozeCheckingServiceManager)
    monkeypatch.setattr(spook, "SpookRepairManager", _NoopSpookRepairManager)
    monkeypatch.setattr(_SnoozeCheckingServiceManager, "had_snoozing", None)

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert _SnoozeCheckingServiceManager.had_snoozing is True, (
        "the actions were registered before the register they reach for"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert DATA_SNOOZING not in hass.data, "the register outlived the entry"


async def test_setup_entry_starts_and_stops_the_run_history(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the config entry owns the run history as well.

    Same reason as the register above: a condition inside an action sequence
    is only built once that sequence runs, and a history that started then
    would have missed the runs it is being asked to count.
    """

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

    # Asserted through behaviour rather than the listener list: the context
    # register listens to the same event, so its presence proves nothing.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    history = async_get_run_history(hass)
    hass.bus.async_fire(EVENT_AUTOMATION_TRIGGERED, {"entity_id": "automation.nightly"})
    await hass.async_block_till_done()
    assert history.async_runs_within("automation.nightly", timedelta(hours=1)) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert history.async_runs_within("automation.nightly", timedelta(hours=1)) == 0

    hass.bus.async_fire(EVENT_AUTOMATION_TRIGGERED, {"entity_id": "automation.nightly"})
    await hass.async_block_till_done()
    assert history.async_runs_within("automation.nightly", timedelta(hours=1)) == 0, (
        "carried on listening after unloading"
    )


async def test_unload_after_start_does_not_remove_fired_one_time_listeners(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unloading after start does not remove fired one-time listeners again."""

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

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    with caplog.at_level(logging.ERROR, logger="homeassistant.core"):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert "Unable to remove unknown job listener" not in caplog.text


def test_link_sub_integrations_creates_links_idempotently_and_unlinks(
    tmp_path: Path,
) -> None:
    """Test sub-integration links are created, skipped, and removed."""
    fake_hass = SimpleNamespace(config=SimpleNamespace(config_dir=tmp_path))
    _create_sub_integration_sources(tmp_path)

    assert link_sub_integrations(fake_hass) is True

    for name in _sub_integration_names():
        link = tmp_path / "custom_components" / name
        assert link.is_symlink()
        assert link.readlink() == (
            tmp_path / "custom_components" / DOMAIN / "integrations" / name
        )

    assert link_sub_integrations(fake_hass) is False

    unlink_sub_integrations(fake_hass)

    for name in _sub_integration_names():
        assert not (tmp_path / "custom_components" / name).exists()


async def test_remove_entry_unlinks_sub_integrations(tmp_path: Path) -> None:
    """Test removing Spook unlinks the sub-integrations."""
    fake_hass = SimpleNamespace(
        config=SimpleNamespace(config_dir=tmp_path),
        async_add_executor_job=AsyncMock(side_effect=lambda func, *args: func(*args)),
    )
    _create_sub_integration_sources(tmp_path)
    assert link_sub_integrations(fake_hass) is True

    await spook.async_remove_entry(fake_hass, MockConfigEntry(domain=DOMAIN, data={}))

    for name in _sub_integration_names():
        assert not (tmp_path / "custom_components" / name).exists()


@pytest.mark.parametrize(
    ("state", "restart_choice"),
    [
        (CoreState.not_running, "later"),
        (CoreState.starting, "later"),
        (CoreState.running, "later"),
        (CoreState.not_running, "now"),
    ],
)
async def test_setup_entry_restart_required_paths(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    state: CoreState,
    restart_choice: str,
) -> None:
    """Test setup behavior when sub-integration linking requires a restart."""
    restart_now = restart_choice == "now"
    original_async_stop = hass.async_stop

    async def async_cleanup_hass() -> None:
        """Stop Home Assistant after the restart request is asserted."""
        monkeypatch.setattr(hass, "state", CoreState.running)
        await original_async_stop()

    async_stop = AsyncMock()

    async def async_forward_no_platforms(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
    ) -> None:
        """Forward no ectoplasm setup during restart tests."""

    async def async_forward_entry_setups_noop(
        _entry: ConfigEntry,
        _platforms: list[str],
    ) -> None:
        """Forward no platform setup during restart tests."""

    def setup_cache_invalidation_noop(_hass: HomeAssistant) -> Callable[[], None]:
        """Skip entity ID cache invalidation listeners during restart tests."""
        return lambda: None

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "async_forward_setup_entry", async_forward_no_platforms)
    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        async_forward_entry_setups_noop,
    )
    monkeypatch.setattr(spook, "SpookServiceManager", _NoopSpookServiceManager)
    monkeypatch.setattr(spook, "SpookRepairManager", _NoopSpookRepairManager)
    monkeypatch.setattr(spook, "link_sub_integrations", _link_sub_integrations_changed)
    monkeypatch.setattr(
        spook,
        "async_setup_all_entity_ids_cache_invalidation",
        setup_cache_invalidation_noop,
    )
    monkeypatch.setattr(hass, "async_stop", async_stop)
    monkeypatch.setattr(hass, "state", state)
    if restart_now:
        hass.data[DOMAIN] = "Boo!"

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)

    result = await spook.async_setup_entry(hass, entry)

    if state == CoreState.running and not restart_now:
        assert result is True
    else:
        assert result is False

    if restart_now or state == CoreState.starting:
        await hass.async_block_till_done()
        hass.async_stop.assert_awaited_once_with(RESTART_EXIT_CODE)
        assert ir.async_get(hass).async_get_issue(DOMAIN, "restart_required") is None
        await async_cleanup_hass()
        return

    if state == CoreState.not_running:
        hass.async_stop.assert_not_called()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        hass.async_stop.assert_awaited_once_with(RESTART_EXIT_CODE)
        assert ir.async_get(hass).async_get_issue(DOMAIN, "restart_required") is None
        await async_cleanup_hass()
        return

    hass.async_stop.assert_not_called()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "restart_required")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "restart_required"
    await original_async_stop()


async def test_repairs_are_set_up_when_loaded_after_start(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test repairs still start when the entry loads after Home Assistant did.

    Reloading the config entry, or setting Spook up for the first time on a
    running instance, re-runs async_setup_entry long after
    EVENT_HOMEASSISTANT_STARTED has fired. Waiting for that event alone leaves
    every repair check dead until a core restart, with nothing in the log.
    """

    async def async_forward_no_platforms(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
    ) -> None:
        """Forward no ectoplasm setup."""

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", _link_sub_integrations_noop)
    monkeypatch.setattr(spook, "async_forward_setup_entry", async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _NoopSpookServiceManager)
    monkeypatch.setattr(spook, "SpookRepairManager", _RecordingSpookRepairManager)
    monkeypatch.setattr(_RecordingSpookRepairManager, "setups", 0)

    hass.set_state(CoreState.running)

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert _RecordingSpookRepairManager.setups == 1


async def test_repairs_are_set_up_once_when_loaded_before_start(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the normal boot path still sets repairs up exactly once."""

    async def async_forward_no_platforms(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
    ) -> None:
        """Forward no ectoplasm setup."""

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", _link_sub_integrations_noop)
    monkeypatch.setattr(spook, "async_forward_setup_entry", async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _NoopSpookServiceManager)
    monkeypatch.setattr(spook, "SpookRepairManager", _RecordingSpookRepairManager)
    monkeypatch.setattr(_RecordingSpookRepairManager, "setups", 0)

    hass.set_state(CoreState.not_running)

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Nothing yet, repairs deliberately wait for a settled instance.
    assert _RecordingSpookRepairManager.setups == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert _RecordingSpookRepairManager.setups == 1
