"""Spook - Your homie. What every tool for an assistant shares.

Only for Home Assistant's own admin API, never for Assist: these read and
change the whole house, which is not something to hand to whoever is
talking to the kitchen speaker.

Each tool lives in a module of its own, under `ectoplasms/*/tools/`, with a
`SpookTool` class. They are found when Spook sets up, and handed out from
there by the `llm` platform.

Home Assistant sends the definition of every tool it hands out along with
every request, and a small model cannot carry many. So only a few are in the
front, with a definition of their own. The rest wait behind one of two
doors, `spook__read` and `spook__change`, which run them by name.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import importlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.llm import (
    Tool,
    ToolAnnotations,
    ToolResult,
    selector_serializer,
)
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from homeassistant.core import CALLBACK_TYPE
    from homeassistant.helpers.llm import LLMContext, ToolInput
    from homeassistant.util.json import JsonObjectType

# Sent along with every single request, so it stays short. The rest is in the
# tool descriptions, which the model only reads when it is looking for a tool.
_PROMPT_INTRODUCTION = (
    "Spook is a Home Assistant integration that finds ghosts: things in this "
    "house that point at something that is not there anymore, or are left "
    "over and unused. Each ghost is a Spook repair issue."
)
_PROMPT_DOORS = (
    "More Spook tools are behind {doors}, which list them when called without a tool."
)

# The tools Spook found when it set up. Core asks for them from a callback,
# which cannot import anything without holding up the event loop.
DATA_TOOLS: HassKey[list[type[AbstractSpookTool]]] = HassKey("spook_tools")

# Read once, on import, which Home Assistant does off the event loop.
_TRANSLATION_LANGUAGES = frozenset(
    path.stem for path in (Path(__file__).parent / "translations").glob("*.json")
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

READ_ONLY = ToolAnnotations(
    read_only=True, destructive=False, idempotent=True, open_world=False
)


class _KeepUnknownPlaceholders(dict[str, str]):
    """Placeholders that leave one nobody filled in standing as it was."""

    def __missing__(self, key: str) -> str:
        """Put the placeholder back, rather than fail the whole sentence."""
        return f"{{{key}}}"


def render(template: str, placeholders: Mapping[str, str]) -> str:
    """Return a translated string with its placeholders filled in.

    A translation can carry a brace that is not a placeholder, and a model is
    better off with the raw sentence than with nothing at all.
    """
    try:
        return template.format_map(_KeepUnknownPlaceholders(placeholders))
    except AttributeError, IndexError, KeyError, ValueError:
        return template


def conversation_language(hass: HomeAssistant, llm_context: LLMContext) -> str:
    """Return the language to answer in.

    A conversation agent can say it takes any language, and then the house's
    own language is the one people read the repairs in anyway.
    """
    if llm_context.language in (None, MATCH_ALL):
        return hass.config.language

    # A regional code like `nl-NL` is still Dutch. Spook's translations only
    # know `nl`, and Home Assistant would fill a language it has no file for
    # with English rather than with its base.
    language = llm_context.language
    base = language.partition("-")[0]
    if language not in _TRANSLATION_LANGUAGES and base in _TRANSLATION_LANGUAGES:
        return base
    return language


def error(message: str, details: JsonObjectType | None = None) -> ToolResult:
    """Return a refusal or failure the model can read and pass on.

    With details, for what helps the model try again right away.
    """
    return ToolResult(data={"error": message, **(details or {})}, error=True)


def first_sentence(text: str) -> str:
    """Return the first sentence, which is what a list of things needs."""
    sentence, period, _ = text.partition(". ")
    return f"{sentence}{period}".strip()


class NotAJsonObjectError(ValueError):
    """JSON that holds something other than an object."""


def unwrap_gemini_object(value: dict[str, Any]) -> dict[str, Any]:
    """Return an object argument, also when it came in as a JSON string.

    Gemini takes no object without fixed properties, so Home Assistant's
    Gemini integration hands it over as an object holding one string, `json`.
    Read as it came, it holds nothing of what was meant.

    Raises a ValueError for a string that is not JSON, and the
    NotAJsonObjectError subclass of it for JSON that is not an object.
    """
    if set(value) != {"json"} or not isinstance(value["json"], str):
        return value

    unwrapped = json.loads(value["json"])
    if not isinstance(unwrapped, dict):
        raise NotAJsonObjectError
    return unwrapped


def tool_schema(tool: type[Tool] | Tool) -> JsonObjectType:
    """Return the parameters of a tool, as a client receives them.

    Converted the way Home Assistant's MCP server does it, so a model that
    sees this sees what it would have seen in the definition.
    """
    converted = probatio.to_openapi(
        tool.parameters,
        custom_serializer=selector_serializer,
        openapi_version="3.1.0",
    )
    schema: JsonObjectType = {"type": "object", "properties": converted["properties"]}
    if required := converted.get("required"):
        schema["required"] = required
    return schema


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class AbstractSpookTool(Tool, ABC):
    """What every Spook tool shares: who may call it, and how."""

    integration = DOMAIN

    #: The integration this tool is about. Only offered while it is loaded.
    domain: str

    #: Whether the definition of this tool goes along with every request.
    #: A tool in the front costs every request its definition, whether the
    #: model uses it or not. One that is not waits behind the door of its
    #: kind, `spook__read` or `spook__change`, which runs it by name. Only
    #: what a model needs to find its way belongs in the front.
    in_front: bool = False

    #: One sentence for the prompt, saying when to use this tool. Only for a
    #: tool in the front, and only when its description is not enough. It
    #: goes along with every request too.
    prompt_hint: str | None = None

    #: Whether this tool is one of the doors. Only the doors set it.
    is_door: bool = False

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Refuse whoever is not an administrator, then do the work.

        Home Assistant keeps the tools it was handed for as long as a
        conversation lasts, so a tool can still be called after Spook
        unloaded. It is asked again here whether it is still on offer.
        """
        if (
            type(self) not in hass.data.get(DATA_TOOLS, ())
            or self.domain not in hass.config.components
        ):
            return error(
                "This tool is not available at the moment: Spook, or what "
                "the tool is about, is not loaded."
            )

        if (refusal := await self._async_refusal(hass, llm_context)) is not None:
            return refusal

        return await self._async_run(
            hass, self.parameters(tool_input.tool_args), llm_context
        )

    async def _async_refusal(
        self, hass: HomeAssistant, llm_context: LLMContext
    ) -> ToolResult | None:
        """Return why this caller may not use the tool, or None if they may.

        The API these are offered on is for administrators already. Asked
        again here anyway, because a tool that changes the house should not
        depend on which API it happened to be handed out by. Something that
        changes things also wants to know who asked: no user, no change.
        """
        user_id = llm_context.context.user_id if llm_context.context else None

        if user_id is None:
            if self.annotations.read_only:
                return None
            return error(
                "Spook only makes changes for a signed-in administrator, "
                "and this request has no user."
            )

        user = await hass.auth.async_get_user(user_id)
        if user is None or not user.is_admin:
            return error("Spook's tools are for administrators only.")

        return None

    @abstractmethod
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """Do what the tool does, with arguments that passed validation."""


async def async_setup_spook_tools(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Find Spook's tools, and keep them for the platform to hand out.

    Returns what puts them away again, so an unloaded Spook offers nothing.
    """
    tools: list[type[AbstractSpookTool]] = []

    def _load_all_tool_modules() -> None:
        """Load all tool modules, isolating failures.

        A tool that fails to import, most likely because Home Assistant
        moved or renamed something it uses, must not take the others down
        with it.
        """
        for module_file in Path(__file__).parent.rglob("ectoplasms/*/tools/*.py"):
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
                    "Spook tool %s.%s failed to load and has been skipped; "
                    "please report this issue at "
                    "https://github.com/frenck/spook/issues",
                    __package__,
                    module_path,
                )
                continue

            tools.append(module.SpookTool)

    await hass.async_add_import_executor_job(_load_all_tool_modules)

    # The files come in whatever order the disk keeps them in. A model gets
    # the same list every time, whatever disk that is.
    hass.data[DATA_TOOLS] = sorted(tools, key=lambda tool: tool.name)

    @callback
    def _async_put_away() -> None:
        """Stop offering the tools of a Spook that is no longer there."""
        hass.data.pop(DATA_TOOLS, None)

    return _async_put_away


@callback
def async_available_tools(hass: HomeAssistant) -> list[type[AbstractSpookTool]]:
    """Return the tools that can run right now, in the front or not.

    A tool about an integration that is not loaded has nothing to work with,
    so it is left out until it is. Nothing at all before Spook set up.
    """
    return [
        tool
        for tool in hass.data.get(DATA_TOOLS, [])
        if tool.domain in hass.config.components
    ]


def build_prompt(tools: Sequence[type[AbstractSpookTool] | AbstractSpookTool]) -> str:
    """Return the prompt for the tools handed out, naming only those."""
    sentences = [_PROMPT_INTRODUCTION]
    sentences.extend(
        tool.prompt_hint for tool in tools if tool.in_front and tool.prompt_hint
    )

    if doors := [tool.name for tool in tools if tool.is_door]:
        sentences.append(_PROMPT_DOORS.format(doors=" and ".join(doors)))

    return " ".join(sentences)


@callback
def async_get_spook_tools(hass: HomeAssistant) -> LLMTools | None:
    """Return Spook's tools and the prompt that goes with them.

    The tools in the front, and a door only once something waits behind it.
    A door with nothing to open would cost every request its definition for
    nothing.
    """
    available = async_available_tools(hass)
    behind_a_door = {
        tool.annotations.read_only
        for tool in available
        if not tool.in_front and not tool.is_door
    }

    tools = [
        tool()
        for tool in available
        if tool.in_front
        or (tool.is_door and tool.annotations.read_only in behind_a_door)
    ]
    if not tools:
        return None

    return LLMTools(tools=tools, prompt=build_prompt(tools))
