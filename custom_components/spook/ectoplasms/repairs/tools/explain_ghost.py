"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.repairs import DOMAIN
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.llm import ToolResult

from ....issue_tools import (
    FixFlowUnavailableError,
    IssueStrings,
    async_fix_flow,
    async_ghost,
    summary,
    unknown_ghost,
)
from ....llm_tools import READ_ONLY, AbstractSpookTool

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir
    from homeassistant.helpers.llm import LLMContext
    from homeassistant.util.json import JsonObjectType


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookTool):
    """Explain one of Spook's repair issues."""

    domain = DOMAIN
    name = "spook__explain_ghost"
    title = "Explain a Spook ghost"
    description = (
        "Explain one Spook repair issue: the full description people see in "
        "the Repairs dashboard, the fix options it offers, and the raw details "
        "Spook worked out, like likely renames of entities that went missing."
    )
    annotations = READ_ONLY
    parameters = probatio.Schema(
        {
            probatio.Required(
                "issue_id", description="The ID of the issue, from spook__list_ghosts."
            ): str,
        }
    )

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """Explain the ghost."""
        if (issue := async_ghost(hass, args["issue_id"])) is None:
            return unknown_ghost(args["issue_id"])

        strings = await IssueStrings.async_load(hass, llm_context)
        data: JsonObjectType = {
            **summary(issue, strings),
            "description": strings.description(issue),
            "fix_options": [],
            "placeholders": dict(issue.translation_placeholders or {}),
        }
        if issue.is_fixable:
            data.update(await self._async_fix_options(hass, issue, strings))

        return ToolResult(data=data)

    @staticmethod
    async def _async_fix_options(
        hass: HomeAssistant, issue: ir.IssueEntry, strings: IssueStrings
    ) -> JsonObjectType:
        """Return what the fix offers right now, by asking the fix itself.

        The translations list every option a fix can have, not the ones it
        has today. A dashboard resource from YAML gets no menu at all, just a
        note saying where the file is, and a model reading the translations
        would offer a button that is not there.
        """
        try:
            async with async_fix_flow(hass, issue) as (_, result):
                if result["type"] is FlowResultType.ABORT:
                    return {"fix_unavailable": strings.abort_reason(issue, result)}

                # A form wants a person in the dashboard, which is not
                # something spook__fix_ghost can be.
                if result["type"] is not FlowResultType.MENU:
                    return {}

                step = result["step_id"]
                placeholders = result.get("description_placeholders")
                return {
                    "fix_options": [
                        {
                            "option": option,
                            "label": strings.render(
                                issue,
                                f"fix_flow.step.{step}.menu_options.{option}",
                                placeholders,
                            )
                            or option,
                        }
                        for option in result["menu_options"]
                    ]
                }
        except FixFlowUnavailableError as err:
            return {"fix_unavailable": str(err)}
