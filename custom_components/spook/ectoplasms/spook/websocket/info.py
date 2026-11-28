"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from homeassistant.loader import async_get_loaded_integration

from ....const import DOMAIN
from ....websocket import AbstractSpookWebSocketCommand

if TYPE_CHECKING:
    from homeassistant.components.websocket_api import ActiveConnection
    from homeassistant.core import HomeAssistant


# A command does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class SpookWebSocketCommand(AbstractSpookWebSocketCommand):
    """Tell which Spook is running."""

    command = "spook/info"
    admin_only = True

    @override
    async def async_handle(
        self,
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Answer with the version of Spook."""
        connection.send_result(
            msg["id"],
            {"version": str(async_get_loaded_integration(hass, DOMAIN).version)},
        )
