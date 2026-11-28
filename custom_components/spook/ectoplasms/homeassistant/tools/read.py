"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.homeassistant import DOMAIN

from ....door_tools import CHANGE_DOOR, READ_DOOR, AbstractSpookDoor
from ....llm_tools import READ_ONLY


# What it does lives in the base it shares with the other door.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookDoor):
    """Run one of Spook's tools that only read."""

    domain = DOMAIN
    name = READ_DOOR
    title = "Run a Spook tool that reads"
    description = (
        "Run one of Spook's tools that only read, by name. There are more of "
        "them than are listed as tools of their own, and which ones depends "
        "on what is set up in this house. Leave out tool to list them, then "
        "call again with the tool and its arguments. A tool that changes "
        f"something runs through {CHANGE_DOOR} instead."
    )
    annotations = READ_ONLY
