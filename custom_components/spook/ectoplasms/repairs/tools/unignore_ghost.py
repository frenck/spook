"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.repairs import DOMAIN

from ....issue_tools import AbstractSpookIgnoreTool


# What it does lives in the base it shares with the other ignore tool.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookIgnoreTool):
    """Stop ignoring one of Spook's issues."""

    domain = DOMAIN
    in_front = True
    name = "spook__unignore_ghost"
    title = "Stop ignoring a Spook ghost"
    description = "Stop ignoring one Spook repair issue, so it shows up again."
    ignore = False
