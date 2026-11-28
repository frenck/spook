"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from homeassistant.helpers.llm import ToolResult

from ....const import DOMAIN
from ....issue_tools import IssueStrings, async_ghosts, kind
from ....llm_tools import READ_ONLY, AbstractSpookTool

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.llm import LLMContext

# Enough to say where to start, without handing over the whole list.
_OLDEST_IN_OVERVIEW = 5


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookTool):
    """Summarize how the house is doing, by Spook's count."""

    domain = DOMAIN
    name = "spook__overview"
    title = "Spook's overview"
    description = (
        "A short summary of Spook's repair issues: how many are open and "
        "ignored per kind, and the oldest open ones. Start here for 'how is "
        "my house doing', then use spook__list_ghosts for the details."
    )
    annotations = READ_ONLY

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """Count the ghosts."""
        ghosts = async_ghosts(hass)
        strings = await IssueStrings.async_load(hass, llm_context)

        kinds: dict[str, dict[str, Any]] = {}
        # Oldest first, so the title each kind is shown with is that of the
        # issue that has been waiting longest.
        for issue in reversed(ghosts):
            counts = kinds.setdefault(
                kind(issue),
                {"example_title": strings.title(issue), "open": 0, "ignored": 0},
            )
            counts["ignored" if issue.dismissed_version else "open"] += 1

        still_open = [issue for issue in ghosts if issue.dismissed_version is None]
        return ToolResult(
            data={
                "total": len(ghosts),
                "open": len(still_open),
                "ignored": len(ghosts) - len(still_open),
                "kinds": kinds,
                "oldest_open": [
                    {
                        "issue_id": issue.issue_id,
                        "kind": kind(issue),
                        "title": strings.title(issue),
                        "created": issue.created.isoformat(),
                    }
                    for issue in still_open[::-1][:_OLDEST_IN_OVERVIEW]
                ],
            }
        )
