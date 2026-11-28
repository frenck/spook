"""Spook - Your homie. Spook's tools for Home Assistant's LLM APIs.

Each tool lives in `ectoplasms/*/tools/`, and what they share in
`llm_tools`. This platform loads on every Home Assistant that has the LLM
integration, which is older than the parts the tools are built from:
`ToolResult` and `ToolAnnotations` came with 2026.10, and the administrator
API they belong to with 2026.11. Importing them anywhere older would fail,
and fill the log with it, so they are only imported where they exist. This
is the one place that decides that, for setting up the tools too.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm

if TYPE_CHECKING:
    from homeassistant.components.llm import LLMTools
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.llm import LLMContext

LLM_API_HOME_ASSISTANT: str = getattr(llm, "LLM_API_HOME_ASSISTANT", "homeassistant")

if hasattr(llm, "ToolResult"):
    from .llm_tools import async_get_spook_tools, async_setup_spook_tools
else:
    async_get_spook_tools = None  # pylint: disable=invalid-name
    async_setup_spook_tools = None  # pylint: disable=invalid-name


async def async_setup_tools(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Find Spook's tools, where this Home Assistant can hold them.

    Here, while Spook sets up, because the platform below is a callback and
    cannot import a thing without holding up the event loop.
    """
    if async_setup_spook_tools is None:
        return

    entry.async_on_unload(await async_setup_spook_tools(hass))


@callback
def async_get_tools(
    hass: HomeAssistant,
    llm_context: LLMContext,  # pylint: disable=unused-argument  # noqa: ARG001
    api_id: str,
) -> LLMTools | None:
    """Return Spook's tools, for Home Assistant's own admin API only."""
    if async_get_spook_tools is None or api_id != LLM_API_HOME_ASSISTANT:
        return None

    return async_get_spook_tools(hass)
