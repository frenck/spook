"""Spook - Your homie. What the two doors share.

A door runs a Spook tool by name, so that tool needs no definition of its
own on every request. Two doors, one that only reads and one that changes
things, because a client like Home Assistant's MCP server in read-only mode
judges a tool by its annotations. One door for everything would have to say
it changes things, and take the read-only tools away with it.

Kept here rather than in one of the doors, so neither imports the other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.helpers.llm import ToolInput, ToolResult

from .const import DOMAIN
from .llm_tools import (
    AbstractSpookTool,
    NotAJsonObjectError,
    async_available_tools,
    error,
    first_sentence,
    tool_schema,
    unwrap_gemini_object,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.llm import LLMContext
    from homeassistant.util.json import JsonObjectType

READ_DOOR = f"{DOMAIN}__read"
CHANGE_DOOR = f"{DOMAIN}__change"

# Enough for every tool there is today, with plenty of room. A list longer
# than this is no longer something to read through, which is what search is
# for.
_LISTED_AT_MOST = 100


def _door_for(tool: type[AbstractSpookTool]) -> str:
    """Return the name of the door a tool runs through."""
    return READ_DOOR if tool.annotations.read_only else CHANGE_DOOR


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class AbstractSpookDoor(AbstractSpookTool):
    """Run one of Spook's tools of one kind, by name."""

    is_door = True
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "tool",
                description=(
                    "The name of the tool to run, as the list gives it. Leave "
                    "it out to get the list."
                ),
            ): str,
            probatio.Optional(
                "arguments",
                description=(
                    "The arguments for that tool, as the JSON object its "
                    "parameters describe."
                ),
                default=dict,
            ): dict,
        }
    )

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """List the tools behind this door, or run one of them."""
        if "tool" not in args:
            return ToolResult(data=self._listing(hass))

        name = args["tool"].strip()
        if not name.startswith(f"{DOMAIN}__"):
            name = f"{DOMAIN}__{name}"

        target = self._target_or_refusal(hass, name)
        if isinstance(target, ToolResult):
            return target

        try:
            arguments = unwrap_gemini_object(args["arguments"])
        except NotAJsonObjectError:
            return error("The arguments should be a JSON object.")
        except ValueError as err:
            return error(f"The arguments are not valid JSON: {err}")

        # Through the tool's own call, so it checks for itself whether it is
        # on offer, who is asking, and what it was handed. Its arguments
        # are the one thing a model gets wrong here without a definition to
        # read, so the answer comes with that definition.
        try:
            return await target().async_call(
                hass, ToolInput(tool_name=name, tool_args=arguments), llm_context
            )
        except probatio.Invalid as err:
            return error(
                f"The arguments for {name} do not fit: {err}",
                {"tool": name, "parameters": tool_schema(target)},
            )

    def _target_or_refusal(
        self, hass: HomeAssistant, name: str
    ) -> type[AbstractSpookTool] | ToolResult:
        """Return the tool to run, or why this door does not run it."""
        found = [tool for tool in async_available_tools(hass) if tool.name == name]
        if not found:
            return error(
                f"Spook has no tool {name!r} on offer here. These are the ones "
                f"{self.name} can run.",
                self._listing(hass),
            )

        target = found[0]
        if target.is_door:
            return error(
                f"{name} is a door itself, and a door does not run a door. "
                f"Call {name} directly."
            )

        if target.annotations.read_only != self.annotations.read_only:
            kind = "only reads" if target.annotations.read_only else "changes things"
            return error(
                f"{name} {kind}, so it runs through {_door_for(target)}, "
                f"not {self.name}. It did not run."
            )

        return target

    def _listing(self, hass: HomeAssistant) -> JsonObjectType:
        """Return the tools this door can run right now, in the same order."""
        tools = [
            tool
            for tool in async_available_tools(hass)
            if not tool.is_door
            and tool.annotations.read_only == self.annotations.read_only
        ]
        return {
            "total": len(tools),
            "tools": [
                {
                    "name": tool.name,
                    "title": tool.title or tool.name,
                    "description": first_sentence(tool.description or ""),
                }
                for tool in tools[:_LISTED_AT_MOST]
            ],
        }
