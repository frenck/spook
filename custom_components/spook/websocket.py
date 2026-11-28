"""Spook - Your homie. What every websocket command of Spook shares.

Each command lives in a module of its own, under `ectoplasms/*/websocket/`,
with a `SpookWebSocketCommand` class. They are found when Spook sets up.

Names are forever once shipped: a frontend out there asks for them by name,
and a renamed command is one that frontend no longer finds. So they follow
one rule, in lower snake case:

- `spook/<area>/<verb>` for a command about one part of Spook, like
  `spook/settings/get` or `spook/repairs/list`.
- `spook/<name>` for the few that are about Spook as a whole, like
  `spook/info`.

Home Assistant has no way to take a websocket command back once it is
registered, and registering one again quietly replaces it. So each command is
registered once for as long as Home Assistant runs, and asks on every call
whether Spook is loaded. One called while it is not answers with an error,
instead of reaching for whatever an unloaded Spook left behind.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE
    from homeassistant.helpers.typing import VolDictType

# The commands of the Spook that is loaded right now, by their name. Gone
# while Spook is not loaded, which is what a command asks before it runs.
DATA_WEBSOCKET_COMMANDS: HassKey[dict[str, type[AbstractSpookWebSocketCommand]]] = (
    HassKey("spook_websocket_commands")
)

# The names registered with Home Assistant, kept across reloads, because
# Home Assistant keeps the commands across reloads too.
DATA_REGISTERED_WEBSOCKET_COMMANDS: HassKey[set[str]] = HassKey(
    "spook_websocket_commands_registered"
)

# The error code of a command called while Spook is not loaded. Its own, so a
# frontend can tell it apart from a command that went wrong.
ERR_NOT_LOADED: Final = "not_loaded"


# A command does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class AbstractSpookWebSocketCommand(ABC):
    """What every Spook websocket command shares: its name, and who may call it.

    `admin_only` has no default on purpose. Every command says for itself
    whether a user without admin rights may call it.
    """

    #: The command's name, following the rule in this module's docstring.
    command: str

    #: Whether only an administrator may call this command.
    admin_only: bool

    #: The fields the message takes, next to `id` and `type`.
    schema: VolDictType | None = None

    @abstractmethod
    async def async_handle(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Handle the command, and answer it on the connection.

        The connection and the message are the ones Home Assistant handed
        over, so a command can answer with a result, an error, or start a
        subscription the way Home Assistant's own commands do.

        A command that starts a subscription has to end it itself when Spook
        unloads. Nothing here does that for it: the refusal of an unloaded
        Spook only covers calls, not what an earlier call left running.
        """


@callback
def _async_register_command(
    hass: HomeAssistant, command: type[AbstractSpookWebSocketCommand]
) -> None:
    """Register a command with Home Assistant, for good.

    The handler looks the command up by its name on every call, rather than
    hold on to the one it was registered with, so it follows Spook through
    reloads and refuses while Spook is not loaded.
    """
    name = command.command

    async def _async_handle(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Hand the message to the command, if Spook is loaded to answer it."""
        if (loaded := hass.data.get(DATA_WEBSOCKET_COMMANDS, {}).get(name)) is None:
            connection.send_error(
                msg["id"],
                ERR_NOT_LOADED,
                f"Spook is not loaded, so {name} cannot be answered right now.",
            )
            return

        await loaded().async_handle(hass, connection, msg)

    handler = websocket_api.websocket_command(
        {vol.Required("type"): name, **(command.schema or {})}
    )(websocket_api.async_response(_async_handle))

    # Home Assistant's own check, which answers with its usual unauthorized
    # error before the command is even scheduled.
    if command.admin_only:
        handler = websocket_api.require_admin(handler)

    websocket_api.async_register_command(hass, handler)


async def async_setup_websocket_commands(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Find Spook's websocket commands, and answer them while Spook is loaded.

    Returns what stops answering them, so an unloaded Spook refuses instead.
    """
    commands: list[type[AbstractSpookWebSocketCommand]] = []

    def _load_all_command_modules() -> None:
        """Load all websocket command modules, isolating failures.

        A command that fails to import, most likely because Home Assistant
        moved or renamed something it uses, must not take the others down
        with it.
        """
        for module_file in Path(__file__).parent.rglob("ectoplasms/*/websocket/*.py"):
            if module_file.name == "__init__.py":
                continue
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace("/", ".")

            try:
                module = importlib.import_module(f".{module_path}", __package__)
            # pylint: disable-next=broad-exception-caught
            except Exception:  # noqa: BLE001
                LOGGER.exception(
                    "Spook websocket command %s.%s failed to load and has been "
                    "skipped; please report this issue at "
                    "https://github.com/frenck/spook/issues",
                    __package__,
                    module_path,
                )
                continue

            commands.append(module.SpookWebSocketCommand)

    await hass.async_add_import_executor_job(_load_all_command_modules)

    registered = hass.data.setdefault(DATA_REGISTERED_WEBSOCKET_COMMANDS, set())
    for command in commands:
        if command.command in registered:
            continue

        _async_register_command(hass, command)
        registered.add(command.command)

    hass.data[DATA_WEBSOCKET_COMMANDS] = {
        command.command: command for command in commands
    }

    @callback
    def _async_stop_answering() -> None:
        """Refuse the commands of a Spook that is no longer there."""
        hass.data.pop(DATA_WEBSOCKET_COMMANDS, None)

    return _async_stop_answering
