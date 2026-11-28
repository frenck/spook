"""Tests for Spook's websocket commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import CoreState
from homeassistant.setup import async_setup_component

from custom_components import spook
from custom_components.spook.const import DOMAIN
from custom_components.spook import websocket
from custom_components.spook.websocket import (
    DATA_WEBSOCKET_COMMANDS,
    ERR_NOT_LOADED,
    AbstractSpookWebSocketCommand,
    async_setup_websocket_commands,
)

if TYPE_CHECKING:
    from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

MANIFEST = json.loads(
    (
        Path(__file__).parents[1] / "custom_components" / DOMAIN / "manifest.json"
    ).read_text()
)


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


@pytest.fixture(name="spook_entry")
async def fixture_spook_entry(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    skip_dependency_setup: None,
) -> MockConfigEntry:
    """Set up Spook as a config entry, with only what the commands need.

    The repairs, actions and platforms stay out: setting them up takes long,
    and the commands do not care whether they are there.
    """
    _ = skip_dependency_setup

    # With dependencies skipped, the websocket API would find no web server.
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
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


async def _ask(
    client: MockHAClientWebSocket, message: dict[str, Any]
) -> dict[str, Any]:
    """Send one command the way the frontend does, and return the answer."""
    await client.send_json_auto_id(message)
    return await client.receive_json()


@pytest.mark.usefixtures("spook_entry")
async def test_info_answers_with_the_version(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test spook/info tells the version in Spook's manifest, and nothing else."""
    response = await _ask(await hass_ws_client(hass), {"type": "spook/info"})

    assert response["success"]
    assert response["result"] == {"version": MANIFEST["version"]}


@pytest.mark.usefixtures("spook_entry")
async def test_info_takes_no_fields(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a command without a schema of its own refuses what it does not take."""
    response = await _ask(
        await hass_ws_client(hass), {"type": "spook/info", "boo": "who is there"}
    )

    assert not response["success"]
    assert response["error"]["code"] == websocket_api.ERR_INVALID_FORMAT


@pytest.mark.usefixtures("spook_entry")
async def test_info_refuses_a_user_without_admin_rights(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test a command for administrators gets Home Assistant's own refusal."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    response = await _ask(client, {"type": "spook/info"})

    assert not response["success"]
    assert response["error"]["code"] == websocket_api.ERR_UNAUTHORIZED


# A command does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class _CommandForEveryone(AbstractSpookWebSocketCommand):
    """A command that a user without admin rights may call."""

    command = "spook/boo"
    admin_only = False

    @override
    async def async_handle(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Answer with a boo."""
        connection.send_result(msg["id"], {"boo": True})


@pytest.mark.usefixtures("spook_entry")
async def test_a_command_for_everyone_answers_a_user_without_admin_rights(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test a command that is not for administrators only is open to the rest.

    The other half of the refusal above: the check is put on the commands
    that ask for it, not on every command.
    """
    hass.data[DATA_WEBSOCKET_COMMANDS][_CommandForEveryone.command] = (
        _CommandForEveryone
    )
    # pylint: disable-next=protected-access
    websocket._async_register_command(hass, _CommandForEveryone)  # noqa: SLF001
    client = await hass_ws_client(hass, hass_read_only_access_token)

    response = await _ask(client, {"type": "spook/boo"})

    assert response["success"]
    assert response["result"] == {"boo": True}


async def test_a_reload_registers_nothing_twice(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    spook_entry: MockConfigEntry,
) -> None:
    """Test the command Home Assistant holds is the same one after a reload.

    Home Assistant has no way to take one back, so a reload that registered
    again would replace it each time. The same one answers after.
    """
    registered = hass.data[websocket_api.DOMAIN]["spook/info"]

    assert await hass.config_entries.async_reload(spook_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.data[websocket_api.DOMAIN]["spook/info"] is registered
    response = await _ask(await hass_ws_client(hass), {"type": "spook/info"})
    assert response["result"] == {"version": MANIFEST["version"]}


async def test_an_unloaded_spook_refuses(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    spook_entry: MockConfigEntry,
) -> None:
    """Test a command called while Spook is not loaded says so, and does nothing.

    Home Assistant keeps the command after Spook unloaded, so it is still
    called. Set up again, it answers again.
    """
    assert await hass.config_entries.async_unload(spook_entry.entry_id)
    await hass.async_block_till_done()
    assert spook_entry.state is ConfigEntryState.NOT_LOADED

    response = await _ask(await hass_ws_client(hass), {"type": "spook/info"})

    assert not response["success"]
    assert response["error"]["code"] == ERR_NOT_LOADED
    assert "Spook is not loaded" in response["error"]["message"]

    assert await hass.config_entries.async_setup(spook_entry.entry_id)
    await hass.async_block_till_done()

    response = await _ask(await hass_ws_client(hass), {"type": "spook/info"})
    assert response["result"] == {"version": MANIFEST["version"]}


async def test_a_command_that_fails_to_import_is_skipped(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a command that cannot be imported is left out, and said so."""
    real_import_module = websocket.importlib.import_module

    def _import_module(name: str, package: str | None = None) -> Any:
        if name.endswith(".websocket.info"):
            msg = "Boo! Home Assistant moved something"
            raise ImportError(msg)
        return real_import_module(name, package)

    monkeypatch.setattr(websocket.importlib, "import_module", _import_module)

    await async_setup_websocket_commands(hass)

    assert "spook/info" not in hass.data[DATA_WEBSOCKET_COMMANDS]
    assert "ectoplasms.spook.websocket.info failed to load" in caplog.text
