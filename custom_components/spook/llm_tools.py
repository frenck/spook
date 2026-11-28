"""Spook - Your homie. What every tool for an assistant shares.

Only for Home Assistant's own admin API, never for Assist: these read and
change the whole house, which is not something to hand to whoever is
talking to the kitchen speaker.

Each tool lives in a module of its own, under `ectoplasms/*/tools/`, with a
`SpookTool` class. They are found when Spook sets up, and handed out from
there by the `llm` platform.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from homeassistant.components.llm import LLMTools
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.llm import Tool, ToolAnnotations, ToolResult
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import CALLBACK_TYPE
    from homeassistant.helpers.llm import LLMContext, ToolInput

# Sent along with every single request, so it stays short. The rest is in the
# tool descriptions, which the model only reads when it is looking for a tool.
PROMPT = (
    "Spook is a Home Assistant integration that finds ghosts: things in this "
    "house that point at something that is not there anymore, or are left "
    "over and unused. Each ghost is a Spook repair issue. Use "
    "spook__find_usages to answer where something is used, and "
    "spook__list_features for the triggers, conditions and actions Spook adds."
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


def error(message: str) -> ToolResult:
    """Return a refusal or failure the model can read and pass on."""
    return ToolResult(data={"error": message}, error=True)


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class AbstractSpookTool(Tool, ABC):
    """What every Spook tool shares: who may call it, and how."""

    integration = DOMAIN

    #: The integration this tool is about. Only offered while it is loaded.
    domain: str

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
                "Spook only changes repairs for a signed-in administrator, "
                "and this request has no user."
            )

        user = await hass.auth.async_get_user(user_id)
        if user is None or not user.is_admin:
            return error("Spook's repairs are for administrators only.")

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
def async_get_spook_tools(hass: HomeAssistant) -> LLMTools | None:
    """Return Spook's tools and the prompt that goes with them.

    A tool about an integration that is not loaded has nothing to work with,
    so it is left out until it is. Nothing at all before Spook set up.
    """
    tools = [
        tool()
        for tool in hass.data.get(DATA_TOOLS, [])
        if tool.domain in hass.config.components
    ]
    if not tools:
        return None

    return LLMTools(tools=tools, prompt=PROMPT)
