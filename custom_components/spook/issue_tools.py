"""Spook - Your homie. What the tools about Spook's own repair issues share.

The tools that list, explain, ignore and fix a ghost, and the overview that
counts them, all read the same issues in the same words. Kept here rather
than in one of those tools, so none of them imports another.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import UnknownFlow, UnknownStep
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.llm import ToolAnnotations, ToolResult
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN
from .core_compat import async_is_issue_hidden
from .llm_tools import AbstractSpookTool, conversation_language, error, render

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from homeassistant.components.repairs import (
        RepairsFlowManager,
        RepairsFlowResult,
    )
    from homeassistant.helpers.llm import LLMContext
    from homeassistant.util.json import JsonObjectType


class IssueStrings:
    """Spook's issue translations, in one language, for one tool call.

    Home Assistant fills in English for anything a language lacks, so a
    missing translation reads in English rather than as a key.
    """

    def __init__(self, strings: dict[str, str]) -> None:
        """Hold the flattened translations."""
        self._strings = strings

    @classmethod
    async def async_load(
        cls, hass: HomeAssistant, llm_context: LLMContext
    ) -> IssueStrings:
        """Load the issue translations for the language of the conversation."""
        language = conversation_language(hass, llm_context)
        return cls(await async_get_translations(hass, language, "issues", {DOMAIN}))

    def _key(self, issue: ir.IssueEntry, path: str) -> str:
        """Return the translation key of a part of the issue."""
        return f"component.{DOMAIN}.issues.{kind(issue)}.{path}"

    def render(
        self,
        issue: ir.IssueEntry,
        path: str,
        extra_placeholders: Mapping[str, str] | None = None,
    ) -> str | None:
        """Return a part of the issue, filled in, or None if it has no such part."""
        if (template := self._strings.get(self._key(issue, path))) is None:
            return None
        return render(template, {**_placeholders(issue), **(extra_placeholders or {})})

    def title(self, issue: ir.IssueEntry) -> str:
        """Return the title, falling back to the ID for one with no translation."""
        return self.render(issue, "title") or issue.issue_id

    def description(self, issue: ir.IssueEntry) -> str | None:
        """Return the description, wherever the issue keeps it.

        A plain issue has one of its own. A fixable one keeps it in the first
        step of its fix flow, because that is where the dialog shows it.
        """
        return self.render(issue, "description") or self.render(
            issue, "fix_flow.step.init.description"
        )

    def abort_reason(self, issue: ir.IssueEntry, result: RepairsFlowResult) -> str:
        """Return why a fix flow stopped, in the words the dialog would use."""
        reason: str = result["reason"]
        return (
            self.render(
                issue,
                f"fix_flow.abort.{reason}",
                result.get("description_placeholders"),
            )
            or reason
        )


def kind(issue: ir.IssueEntry) -> str:
    """Return the kind of ghost: the repair that raised it."""
    return issue.translation_key or issue.issue_id


def _placeholders(issue: ir.IssueEntry) -> dict[str, str]:
    """Return everything a string of the issue can be filled in with.

    The fix flow dialogs take their placeholders from the issue's data, the
    issue itself from its placeholders. Both, so each string finds its own.
    """
    data = {key: str(value) for key, value in (issue.data or {}).items()}
    return {**data, **(issue.translation_placeholders or {})}


@callback
def async_ghosts(hass: HomeAssistant) -> list[ir.IssueEntry]:
    """Return Spook's issues that are actually up, newest first.

    An issue that is not active is the empty record Home Assistant keeps to
    remember an ignore over a restart. One of a disabled config entry is
    hidden by Home Assistant until the entry is enabled again. Nobody can see
    either, so neither can this.
    """
    issue_registry = ir.async_get(hass)
    ghosts = [
        issue
        for (domain, _), issue in issue_registry.issues.items()
        if domain == DOMAIN
        and issue.active
        and not async_is_issue_hidden(issue_registry, issue)
    ]
    return sorted(ghosts, key=lambda issue: issue.created, reverse=True)


@callback
def async_ghost(hass: HomeAssistant, issue_id: str) -> ir.IssueEntry | None:
    """Return one of Spook's issues that is up, by ID."""
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    if (
        issue is None
        or not issue.active
        or async_is_issue_hidden(issue_registry, issue)
    ):
        return None
    return issue


def unknown_ghost(issue_id: str) -> ToolResult:
    """Return the answer for an issue ID that is not one of Spook's."""
    return error(
        f"There is no open Spook issue with the ID {issue_id!r}. "
        "Use spook__list_ghosts to see which ones there are."
    )


def summary(issue: ir.IssueEntry, strings: IssueStrings) -> JsonObjectType:
    """Return what every tool says about an issue, at the least."""
    return {
        "issue_id": issue.issue_id,
        "kind": kind(issue),
        "title": strings.title(issue),
        "severity": str(issue.severity),
        "ignored": issue.dismissed_version is not None,
        "is_fixable": issue.is_fixable,
        "learn_more_url": issue.learn_more_url,
        "created": issue.created.isoformat(),
    }


class FixFlowUnavailableError(Exception):
    """A fix flow that could not even be started."""


@asynccontextmanager
async def async_fix_flow(
    hass: HomeAssistant, issue: ir.IssueEntry
) -> AsyncIterator[tuple[RepairsFlowManager, RepairsFlowResult]]:
    """Start an issue's fix flow, and make sure it is gone afterwards.

    Through Home Assistant's own flow manager, so the flow runs exactly as it
    would from the dashboard, the checks it does before it deletes anything
    included.
    """
    if (manager := repairs_flow_manager(hass)) is None:
        msg = "Home Assistant's repairs are not set up."
        raise FixFlowUnavailableError(msg)

    # The issue ID goes in both. Up to Core 2026.9 the flow manager only reads
    # it from the data, and asserts it is there. From 2026.10 it reads it from
    # the context, and copies it into the data by itself. Once Spook requires
    # Core 2026.10 or later, the data can go.
    try:
        result = await manager.async_init(
            DOMAIN,
            context={"issue_id": issue.issue_id},
            data={"issue_id": issue.issue_id},
        )
    except UnknownStep as err:
        raise FixFlowUnavailableError(str(err)) from err

    try:
        yield manager, result
    finally:
        # A flow that ended is gone already. One that did not would hang
        # around waiting for an answer that is never coming.
        with suppress(UnknownFlow):
            manager.async_abort(result["flow_id"])


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class AbstractSpookIgnoreTool(AbstractSpookTool):
    """Ignore or stop ignoring one issue, like the Repairs dashboard does."""

    annotations = ToolAnnotations(
        read_only=False, destructive=False, idempotent=True, open_world=False
    )
    parameters = probatio.Schema(
        {
            probatio.Required(
                "issue_id", description="The ID of the issue, from spook__list_ghosts."
            ): str,
        }
    )

    #: Whether this tool ignores the issue, or takes that back.
    ignore: bool

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """Ignore the issue, or take that back.

        Done through Home Assistant, as the dashboard does it. Spook follows
        the issue registry and writes the decision down itself, so it holds
        even when the issue changes or comes back later.
        """
        if (issue := async_ghost(hass, args["issue_id"])) is None:
            return unknown_ghost(args["issue_id"])

        ir.async_ignore_issue(hass, DOMAIN, issue.issue_id, ignore=self.ignore)
        return ToolResult(data={"issue_id": issue.issue_id, "ignored": self.ignore})
