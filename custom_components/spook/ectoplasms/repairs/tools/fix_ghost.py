"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.repairs import DOMAIN
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.llm import ToolAnnotations, ToolResult

from ....issue_tools import (
    FixFlowUnavailableError,
    IssueStrings,
    async_fix_flow,
    async_ghost,
    unknown_ghost,
)
from ....llm_tools import AbstractSpookTool, error

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir
    from homeassistant.helpers.llm import LLMContext


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookTool):
    """Run one fix option of an issue's fix flow."""

    domain = DOMAIN
    name = "spook__fix_ghost"
    title = "Fix a Spook ghost"
    description = (
        "Run one fix option of a fixable Spook repair issue, the same as "
        "choosing it in the Repairs dashboard. This can delete things, like "
        "an empty area or an unused label, so confirm with the user first. "
        "Use spook__explain_ghost to see the options."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=False, open_world=False
    )
    parameters = probatio.Schema(
        {
            probatio.Required(
                "issue_id", description="The ID of the issue, from spook__list_ghosts."
            ): str,
            probatio.Required(
                "option",
                description=(
                    "The fix option to run, one of the options "
                    "spook__explain_ghost lists for the issue."
                ),
            ): str,
        }
    )

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """Start the fix flow, choose the option, and say how it ended.

        Only a menu is something this can answer; a flow that wants a form
        filled in is left to a person.
        """
        if (issue := async_ghost(hass, args["issue_id"])) is None:
            return unknown_ghost(args["issue_id"])
        if not issue.is_fixable:
            return error(f"The issue {issue.issue_id!r} has no fix to run.")

        strings = await IssueStrings.async_load(hass, llm_context)

        try:
            async with async_fix_flow(hass, issue) as (manager, started):
                if started["type"] is not FlowResultType.MENU:
                    return self._outcome(issue, started, strings)

                offered = list(started["menu_options"])
                if args["option"] not in offered:
                    return error(
                        f"The fix for {issue.issue_id!r} does not offer "
                        f"{args['option']!r}. It offers: {', '.join(offered)}."
                    )

                finished = await manager.async_configure(
                    started["flow_id"], {"next_step_id": args["option"]}
                )
                return self._outcome(issue, finished, strings)
        except FixFlowUnavailableError as err:
            return error(str(err))

    def _outcome(
        self, issue: ir.IssueEntry, result: Any, strings: IssueStrings
    ) -> ToolResult:
        """Return how the fix ended, in the words the dialog would use."""
        if result["type"] is FlowResultType.CREATE_ENTRY:
            return ToolResult(data={"issue_id": issue.issue_id, "outcome": "fixed"})

        if result["type"] is FlowResultType.ABORT:
            return ToolResult(
                data={
                    "issue_id": issue.issue_id,
                    "outcome": "aborted",
                    "reason": result["reason"],
                    "message": strings.abort_reason(issue, result),
                }
            )

        return error(
            "This fix asks for more than a choice from a menu. Open the issue "
            "in the Repairs dashboard to finish it."
        )
