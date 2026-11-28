"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers.llm import ToolAnnotations

from ....door_tools import CHANGE_DOOR, READ_DOOR, AbstractSpookDoor


# What it does lives in the base it shares with the other door.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookDoor):
    """Run one of Spook's tools that change something."""

    domain = DOMAIN
    name = CHANGE_DOOR
    title = "Run a Spook tool that changes things"
    description = (
        "Run one of Spook's tools that change something in this house, by "
        "name. There are more of them than are listed as tools of their own, "
        "and which ones depends on what is set up in this house. Leave out "
        "tool to list them, then call again with the tool and its arguments. "
        "Some of them delete things, so confirm with the user first. A tool "
        f"that only reads runs through {READ_DOOR} instead."
    )
    # A door is as bad as the worst it can run: it could be anything that
    # changes the house, deleting included.
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=False, open_world=False
    )
