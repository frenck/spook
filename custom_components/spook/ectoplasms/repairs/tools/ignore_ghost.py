"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.repairs import DOMAIN

from ....issue_tools import AbstractSpookIgnoreTool


# What it does lives in the base it shares with the other ignore tool.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookIgnoreTool):
    """Ignore one of Spook's issues."""

    domain = DOMAIN
    in_front = True
    name = "spook__ignore_ghost"
    title = "Ignore a Spook ghost"
    description = (
        "Ignore one Spook repair issue, the same as selecting ignore in the "
        "Repairs dashboard. Spook keeps quiet about it until it finds "
        "something new."
    )
    ignore = True
