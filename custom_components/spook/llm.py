"""Spook - Your homie. Spook's tools for Home Assistant's LLM APIs.

The tools live in `llm_tools`. This platform loads on every Home Assistant
that has the LLM integration, which is older than the parts the tools are
built from: `ToolResult` and `ToolAnnotations` came with 2026.10, and the
administrator API they belong to with 2026.11. Importing them anywhere older
would fail, and fill the log with it, so they are only imported where they
exist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm

if TYPE_CHECKING:
    from homeassistant.components.llm import LLMTools
    from homeassistant.helpers.llm import LLMContext

LLM_API_HOME_ASSISTANT: str = getattr(llm, "LLM_API_HOME_ASSISTANT", "homeassistant")

if hasattr(llm, "ToolResult"):
    from .llm_tools import async_get_spook_tools
else:
    async_get_spook_tools = None  # pylint: disable=invalid-name


@callback
def async_get_tools(
    hass: HomeAssistant,  # pylint: disable=unused-argument  # noqa: ARG001
    llm_context: LLMContext,  # pylint: disable=unused-argument  # noqa: ARG001
    api_id: str,
) -> LLMTools | None:
    """Return Spook's tools, for Home Assistant's own admin API only."""
    if async_get_spook_tools is None or api_id != LLM_API_HOME_ASSISTANT:
        return None

    return async_get_spook_tools()
