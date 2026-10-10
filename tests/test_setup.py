"""Tests for the Spook config entry setup."""

from __future__ import annotations

import asyncio

from datetime import timedelta
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
import json
import logging
import sys

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    RESTART_EXIT_CODE,
)
from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.core import Context, CoreState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import (
    IntegrationNotFound,
    async_get_custom_components,
    async_get_integration,
)

import custom_components
from custom_components import spook
from custom_components.spook.automation_runs import async_get_automation_runs
from custom_components.spook.const import DOMAIN
from custom_components.spook.run_history import async_get_run_history
from custom_components.spook.timed_states import DATA_TIMED_STATES
from custom_components.spook.integration_linking import (
    link_sub_integrations,
    unlink_sub_integrations,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

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


class _RegisterCheckingServiceManager:
    """Service manager that records what was in place before it registered."""

    had_the_register: bool | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the checking service manager."""
        self.hass = hass

    async def async_setup(self) -> None:
        """Record whether the timed-state register was already there."""
        type(self).had_the_register = DATA_TIMED_STATES in self.hass.data

    def async_on_unload(self) -> None:
        """Unload no services."""


class _FailingSpookServiceManager:
    """Service manager that fails halfway through setting up."""

    unloads = 0

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the failing service manager."""
        self.hass = hass

    async def async_setup(self) -> None:
        """Fail, as an injection that raised would."""
        msg = "Boo! Halfway through"
        raise RuntimeError(msg)

    def async_on_unload(self) -> None:
        """Record that it was torn down."""
        type(self).unloads += 1


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


def _link_sub_integrations_noop(_hass: HomeAssistant) -> set[str]:
    """Skip sub-integration symlink creation during lifecycle tests."""
    return set()


def _link_spook_inverse(_hass: HomeAssistant) -> set[str]:
    """Pretend the inverse sub integration was linked again."""
    return {"spook_inverse"}


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


async def test_a_service_setup_that_fails_is_torn_down(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test services that fail to set up are unloaded again.

    By then the manager is already listening for components that load later.
    Left like that, it would go on registering actions for a Spook that
    never loaded.
    """

    async def async_forward_no_platforms(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
    ) -> None:
        """Forward no ectoplasm setup."""

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", _link_sub_integrations_noop)
    monkeypatch.setattr(spook, "async_forward_setup_entry", async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _FailingSpookServiceManager)
    monkeypatch.setattr(spook, "SpookRepairManager", _NoopSpookRepairManager)

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert _FailingSpookServiceManager.unloads == 1


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


async def test_setup_entry_has_the_register_before_the_actions(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the timed-state register is in place before any action can be called.

    `automation.snooze` and `automation.turn_on_for` reach for it the moment
    somebody calls one, so registering the actions first leaves a window where
    the action exists and the register does not. That window is a real one: an
    automation set off by Home Assistant starting can call it.
    """

    async def async_forward_no_platforms(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
    ) -> None:
        """Forward no ectoplasm setup during the lifecycle smoke test."""

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", _link_sub_integrations_noop)
    monkeypatch.setattr(spook, "async_forward_setup_entry", async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _RegisterCheckingServiceManager)
    monkeypatch.setattr(spook, "SpookRepairManager", _NoopSpookRepairManager)
    monkeypatch.setattr(_RegisterCheckingServiceManager, "had_the_register", None)

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert _RegisterCheckingServiceManager.had_the_register is True, (
        "the actions were registered before the register they reach for"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert DATA_TIMED_STATES not in hass.data, "the register outlived the entry"


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

    assert link_sub_integrations(fake_hass) == set(_sub_integration_names())

    for name in _sub_integration_names():
        link = tmp_path / "custom_components" / name
        assert link.is_symlink()
        assert link.readlink() == (
            tmp_path / "custom_components" / DOMAIN / "integrations" / name
        )

    assert link_sub_integrations(fake_hass) == set()

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
    assert link_sub_integrations(fake_hass)

    await spook.async_remove_entry(fake_hass, MockConfigEntry(domain=DOMAIN, data={}))

    for name in _sub_integration_names():
        assert not (tmp_path / "custom_components" / name).exists()


_FRESH_SUB_INTEGRATION = "spook_freshly_linked"


@pytest.fixture(name="fresh_sub_integration")
def fixture_fresh_sub_integration(
    hass: HomeAssistant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Callable[[], None]]:
    """Return a callable that links a sub integration nothing has seen yet.

    The test config dir is shared, and other tests leave the real sub
    integrations linked in it. A name of its own keeps this one new to the
    loader, which is the point.
    """
    source = tmp_path / _FRESH_SUB_INTEGRATION
    source.mkdir()
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "domain": _FRESH_SUB_INTEGRATION,
                "name": "Spook freshly linked",
                "codeowners": [],
                "config_flow": True,
                "documentation": "https://spook.boo",
                "integration_type": "helper",
                "iot_class": "calculated",
                "version": "0.0.0",
            }
        )
    )
    (source / "__init__.py").write_text('"""Spook freshly linked."""\n')
    (source / "config_flow.py").write_text(
        dedent(
            f"""\
            \"\"\"Config flow for a freshly linked sub integration.\"\"\"

            from homeassistant.config_entries import ConfigFlow


            class FreshlyLinkedConfigFlow(ConfigFlow, domain="{_FRESH_SUB_INTEGRATION}"):
                \"\"\"Show one form.\"\"\"

                async def async_step_user(self, user_input=None):
                    \"\"\"Show the form.\"\"\"
                    return self.async_show_form(step_id="user")
            """
        )
    )

    custom_components_dir = Path(hass.config.config_dir) / "custom_components"
    custom_components_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(
        custom_components,
        "__path__",
        [*custom_components.__path__, str(custom_components_dir)],
    )
    link = custom_components_dir / _FRESH_SUB_INTEGRATION

    def link_fresh_sub_integration() -> None:
        """Link it in, the way Spook does on a fresh install."""
        link.symlink_to(source, target_is_directory=True)

    yield link_fresh_sub_integration

    link.unlink(missing_ok=True)
    sys.modules.pop(f"custom_components.{_FRESH_SUB_INTEGRATION}", None)
    sys.modules.pop(f"custom_components.{_FRESH_SUB_INTEGRATION}.config_flow", None)


async def test_setup_entry_loads_freshly_linked_sub_integration(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    fresh_sub_integration: Callable[[], None],
) -> None:
    """Test a sub integration linked during setup loads without a restart.

    The loader scans custom_components once and keeps that list. A sub
    integration linked in after the scan is unknown to it, which is why Spook
    used to ask for a restart. Spook now has the loader scan again.
    """

    def link_and_report_a_change(_hass: HomeAssistant) -> set[str]:
        """Link the fresh sub integration, and report it."""
        fresh_sub_integration()
        return {_FRESH_SUB_INTEGRATION}

    async def async_forward_no_platforms(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
    ) -> None:
        """Forward no ectoplasm setup."""

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "async_forward_setup_entry", async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _NoopSpookServiceManager)
    monkeypatch.setattr(spook, "SpookRepairManager", _NoopSpookRepairManager)
    monkeypatch.setattr(spook, "link_sub_integrations", link_and_report_a_change)

    # The scan has happened, as it has on any running Home Assistant.
    assert _FRESH_SUB_INTEGRATION not in await async_get_custom_components(hass)

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    integration = await async_get_integration(hass, _FRESH_SUB_INTEGRATION)
    assert integration.config_flow
    assert ir.async_get(hass).async_get_issue(DOMAIN, "restart_required") is None

    result = await hass.config_entries.flow.async_init(
        _FRESH_SUB_INTEGRATION,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_freshly_linked_sub_integration_unknown_without_rescan(
    hass: HomeAssistant,
    fresh_sub_integration: Callable[[], None],
) -> None:
    """Test the loader misses a sub integration linked after its scan.

    This is the premise the rescan in setup rests on. Should the loader ever
    look again by itself, this fails, and the rescan can go.
    """
    await async_get_custom_components(hass)
    fresh_sub_integration()

    with pytest.raises(IntegrationNotFound):
        await async_get_integration(hass, _FRESH_SUB_INTEGRATION)


def _patch_setup_for_restart_tests(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strip setup down to the sub integration linking."""

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
    monkeypatch.setattr(spook, "link_sub_integrations", _link_spook_inverse)
    monkeypatch.setattr(
        spook,
        "async_setup_all_entity_ids_cache_invalidation",
        setup_cache_invalidation_noop,
    )


@pytest.mark.parametrize(
    "state",
    [CoreState.not_running, CoreState.starting, CoreState.running],
)
async def test_setup_entry_restarts_for_helpers_left_without_their_link(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    state: CoreState,
) -> None:
    """Test a helper whose sub integration link went missing gets a restart.

    Home Assistant found nothing to set the helper up with when it started,
    and does not try again. Linking and rescanning is too late for it.
    """
    _patch_setup_for_restart_tests(hass, monkeypatch)
    original_async_stop = hass.async_stop
    async_stop = AsyncMock()
    monkeypatch.setattr(hass, "async_stop", async_stop)
    monkeypatch.setattr(hass, "state", state)

    MockConfigEntry(domain="spook_inverse", data={}).add_to_hass(hass)
    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)

    result = await spook.async_setup_entry(hass, entry)

    assert result is (state == CoreState.running)

    if state == CoreState.not_running:
        async_stop.assert_not_called()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    await hass.async_block_till_done()

    if state == CoreState.running:
        async_stop.assert_not_called()
        issue = ir.async_get(hass).async_get_issue(DOMAIN, "restart_required")
        assert issue is not None
        assert issue.severity is ir.IssueSeverity.WARNING
        assert issue.translation_key == "restart_required"
        await original_async_stop()
        return

    async_stop.assert_awaited_once_with(RESTART_EXIT_CODE)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "restart_required") is None
    monkeypatch.setattr(hass, "state", CoreState.running)
    await original_async_stop()


@pytest.mark.parametrize(
    ("entry_state", "disabled_by"),
    [
        (ConfigEntryState.LOADED, None),
        (ConfigEntryState.SETUP_RETRY, None),
        (ConfigEntryState.SETUP_ERROR, None),
        (ConfigEntryState.NOT_LOADED, ConfigEntryDisabler.USER),
    ],
)
async def test_setup_entry_does_not_restart_for_helpers_not_waiting(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    entry_state: ConfigEntryState,
    disabled_by: ConfigEntryDisabler | None,
) -> None:
    """Test a helper that is not left waiting is no reason to restart.

    A loaded one runs on code already in memory, the link is only back for
    the next start. One that failed or retries had its code found and run, a
    restart changes nothing for it. A disabled one is not meant to be set up
    at all.
    """
    _patch_setup_for_restart_tests(hass, monkeypatch)
    original_async_stop = hass.async_stop
    async_stop = AsyncMock()
    monkeypatch.setattr(hass, "async_stop", async_stop)
    monkeypatch.setattr(hass, "state", CoreState.starting)

    MockConfigEntry(
        domain="spook_inverse",
        data={},
        state=entry_state,
        disabled_by=disabled_by,
    ).add_to_hass(hass)
    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)

    assert await spook.async_setup_entry(hass, entry) is True
    await hass.async_block_till_done()

    async_stop.assert_not_called()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "restart_required") is None

    monkeypatch.setattr(hass, "state", CoreState.running)
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


async def test_repairs_still_starting_when_spook_unloads_are_torn_down(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test repairs set up after Spook already went are torn down at once.

    Repairs start once Home Assistant has, and starting them takes a moment.
    Disabling or reloading Spook in that moment used to finish first, and the
    repairs carried on starting afterwards with nothing left to stop them:
    inspecting a disabled Spook, or running twice next to the reloaded one.
    """

    async def async_forward_no_platforms(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
    ) -> None:
        """Forward no ectoplasm setup during the lifecycle smoke test."""

    starting = asyncio.Event()
    carry_on = asyncio.Event()
    torn_down: list[bool] = []

    class _SlowSpookRepairManager(_NoopSpookRepairManager):
        """Repair manager that takes its time to start."""

        async def async_setup(self) -> None:
            starting.set()
            await carry_on.wait()

        async def async_on_unload(self) -> None:
            torn_down.append(True)

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", _link_sub_integrations_noop)
    monkeypatch.setattr(spook, "async_forward_setup_entry", async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _NoopSpookServiceManager)
    monkeypatch.setattr(spook, "SpookRepairManager", _SlowSpookRepairManager)
    monkeypatch.setattr(hass, "state", CoreState.starting)

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await starting.wait()

    assert await hass.config_entries.async_unload(entry.entry_id)
    carry_on.set()
    await hass.async_block_till_done()

    assert torn_down == [True]
