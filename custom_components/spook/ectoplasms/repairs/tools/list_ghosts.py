"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.repairs import DOMAIN
from homeassistant.helpers.llm import ToolResult

from ....issue_tools import IssueStrings, async_ghosts, kind, summary
from ....llm_tools import DEFAULT_LIMIT, MAX_LIMIT, READ_ONLY, AbstractSpookTool

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.llm import LLMContext


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookTool):
    """List Spook's open repair issues."""

    domain = DOMAIN
    in_front = True
    name = "spook__list_ghosts"
    title = "List Spook's ghosts"
    description = (
        "List the open repair issues Spook raised: references to entities, "
        "actions, areas, devices and more that do not exist anymore, and "
        "leftovers like empty areas or unused labels. Newest first. Ignored "
        "ones are left out unless asked for."
    )
    annotations = READ_ONLY
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "kind",
                description=(
                    "Only issues of this kind, like "
                    "'automation_unknown_entity_references' or 'unused_labels'."
                ),
            ): str,
            probatio.Optional(
                "include_ignored",
                description="Also list issues somebody ignored (default: false).",
                default=False,
                # Pylint reads the validator factory as the validator itself.
                # pylint: disable-next=no-value-for-parameter
            ): probatio.All(probatio.Boolean(), bool),
            probatio.Optional(
                "limit",
                description=(
                    "Maximum number of issues to return "
                    f"(default: {DEFAULT_LIMIT}, max: {MAX_LIMIT})."
                ),
                default=DEFAULT_LIMIT,
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=MAX_LIMIT)),
        }
    )

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """List the ghosts."""
        ghosts = [
            issue
            for issue in async_ghosts(hass)
            if (args["include_ignored"] or issue.dismissed_version is None)
            and args.get("kind") in (None, kind(issue))
        ]

        strings = await IssueStrings.async_load(hass, llm_context)
        return ToolResult(
            data={
                "total": len(ghosts),
                "ghosts": [
                    summary(issue, strings) for issue in ghosts[: args["limit"]]
                ],
            }
        )
