"""Tests for serving the files Spook's frontends are built into."""

from __future__ import annotations

from http import HTTPStatus
import logging
from typing import TYPE_CHECKING

from aiohttp import hdrs, web
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import CoreState
from homeassistant.setup import async_setup_component

from custom_components import spook
from custom_components.spook import static_files
from custom_components.spook.const import DOMAIN
from custom_components.spook.static_files import STATIC_URL

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_homeassistant.typing import ClientSessionGenerator

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

BUNDLE = f"{STATIC_URL}/dashboard/spook.js"


class _NoServices:
    """Service manager that sets up no actions."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the service manager."""
        self.hass = hass

    async def async_setup(self) -> None:
        """Set up no services."""

    def async_on_unload(self) -> None:
        """Unload no services."""


class _NoRepairs:
    """Repair manager that sets up no repairs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair manager."""
        self.hass = hass

    async def async_setup(self, *, spread_first_inspections: bool = False) -> None:
        """Set up no repairs."""

    async def async_on_unload(self) -> None:
        """Unload no repairs."""


@pytest.fixture(name="static_path")
def fixture_static_path() -> Path:
    """Return where Spook looks for its built files in this test, not built yet.

    Not the checkout's: `no_built_frontends` in the conftest points it at a
    directory of the test's own.
    """
    return static_files.STATIC_PATH


def _build(static_path: Path) -> None:
    """Put a dashboard bundle where a build puts it."""
    (static_path / "dashboard").mkdir(parents=True)
    (static_path / "dashboard" / "spook.js").write_text("// Boo!\n")


@pytest.fixture(name="set_up_spook")
async def fixture_set_up_spook(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    skip_dependency_setup: None,
) -> MockConfigEntry:
    """Have Spook ready to set up as a config entry, with only what serving needs.

    The repairs, actions and platforms stay out: setting them up takes long,
    and serving files does not care whether they are there.
    """
    _ = skip_dependency_setup

    # With dependencies skipped, there would be no web server to serve from.
    assert await async_setup_component(hass, "http", {})

    async def _async_forward_no_platforms(
        _hass: HomeAssistant, _entry: ConfigEntry
    ) -> None:
        """Forward no ectoplasm setup."""

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", lambda _hass: set())
    monkeypatch.setattr(spook, "async_forward_setup_entry", _async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _NoServices)
    monkeypatch.setattr(spook, "SpookRepairManager", _NoRepairs)
    hass.set_state(CoreState.running)

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)
    return entry


async def _set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set Spook up, and wait for it to be done."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _directories_served(hass: HomeAssistant) -> int:
    """Count how often Home Assistant serves the directory of Spook's files."""
    return sum(
        1
        for resource in hass.http.app.router.resources()
        if isinstance(resource, web.StaticResource) and resource.canonical == STATIC_URL
    )


async def test_the_built_files_are_served(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    static_path: Path,
    set_up_spook: MockConfigEntry,
) -> None:
    """Test a built bundle is served, to anyone, with cache headers.

    No login: a browser loads the files of a page before it has one, the
    way it loads the frontend's own.
    """
    _build(static_path)

    await _set_up(hass, set_up_spook)

    response = await (await hass_client_no_auth()).get(BUNDLE)
    assert response.status == HTTPStatus.OK
    assert await response.text() == "// Boo!\n"
    assert "max-age" in response.headers[hdrs.CACHE_CONTROL]


async def test_nothing_is_served_without_a_build(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    static_path: Path,
    set_up_spook: MockConfigEntry,
) -> None:
    """Test a checkout without a build sets up as a backend, and says so once.

    Only at debug level: a checkout that nobody built is how most people
    who run Spook from git have it, and not something to fix.
    """
    with caplog.at_level(logging.DEBUG, logger="custom_components.spook"):
        await _set_up(hass, set_up_spook)

    assert _directories_served(hass) == 0
    response = await (await hass_client_no_auth()).get(BUNDLE)
    assert response.status == HTTPStatus.NOT_FOUND

    messages = [
        record
        for record in caplog.records
        if record.name.startswith("custom_components.spook")
        and str(static_path) in record.getMessage()
    ]
    assert len(messages) == 1
    assert messages[0].levelno == logging.DEBUG


async def test_a_reload_serves_the_files_once(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    static_path: Path,
    set_up_spook: MockConfigEntry,
) -> None:
    """Test a reload of Spook does not add a second route for its files.

    aiohttp takes the same path twice without a word, and keeps answering
    from the first. Each reload would leave one more behind.
    """
    _build(static_path)
    await _set_up(hass, set_up_spook)

    assert await hass.config_entries.async_reload(set_up_spook.entry_id)
    await hass.async_block_till_done()

    assert _directories_served(hass) == 1
    response = await (await hass_client_no_auth()).get(BUNDLE)
    assert response.status == HTTPStatus.OK


async def test_a_reload_serves_what_was_built_since(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    static_path: Path,
    set_up_spook: MockConfigEntry,
) -> None:
    """Test a build made while Spook runs is served after a reload of Spook.

    That is how working on a frontend goes: start Home Assistant, build,
    reload. A restart is not needed.
    """
    await _set_up(hass, set_up_spook)
    _build(static_path)

    assert await hass.config_entries.async_reload(set_up_spook.entry_id)
    await hass.async_block_till_done()

    response = await (await hass_client_no_auth()).get(BUNDLE)
    assert response.status == HTTPStatus.OK
