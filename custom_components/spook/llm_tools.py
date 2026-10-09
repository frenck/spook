"""Spook - Your homie. Tools for an assistant that goes ghost hunting.

Only for Home Assistant's own admin API, never for Assist: these read and
change the repairs of the whole house, which is not something to hand to
whoever is talking to the kitchen speaker.
"""

from __future__ import annotations

from abc import abstractmethod
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow, UnknownStep
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.llm import Tool, ToolAnnotations, ToolResult
from homeassistant.helpers.translation import async_get_translations

from .condition import async_get_conditions
from .const import DOMAIN
from .draft_checking import (
    DRAFT_KINDS,
    DraftError,
    async_check_draft,
    async_describe_unknown_entities,
)
from .trigger import async_get_triggers
from .usage_finding import REFERENCE_TYPES, async_find_usages, reference_types_for

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable, Mapping

    from homeassistant.components.repairs import (
        RepairsFlowManager,
        RepairsFlowResult,
    )
    from homeassistant.helpers.llm import LLMContext, ToolInput
    from homeassistant.util.json import JsonObjectType

# Sent along with every single request, so it stays short. The rest is in the
# tool descriptions, which the model only reads when it is looking for a tool.
PROMPT = (
    "Spook is a Home Assistant integration that finds ghosts: things in this "
    "house that point at something that is not there anymore, or are left "
    "over and unused. Each ghost is a Spook repair issue. Use "
    "spook__find_usages to answer where something is used, and "
    "spook__list_features for the triggers, conditions and actions Spook adds."
)

# Read once, when Home Assistant imports this platform, which it does off the
# event loop.
_TRANSLATION_LANGUAGES = frozenset(
    path.stem for path in (Path(__file__).parent / "translations").glob("*.json")
)

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200

# Enough to say where to start, without handing over the whole list.
_OLDEST_IN_OVERVIEW = 5

_FEATURE_KINDS = ("triggers", "conditions", "actions")

_READ_ONLY = ToolAnnotations(
    read_only=True, destructive=False, idempotent=True, open_world=False
)


# A tool is one thing it does, so every one of them has one method to show.
# pylint: disable=too-few-public-methods


class _KeepUnknownPlaceholders(dict[str, str]):
    """Placeholders that leave one nobody filled in standing as it was."""

    def __missing__(self, key: str) -> str:
        """Put the placeholder back, rather than fail the whole sentence."""
        return f"{{{key}}}"


def _render(template: str, placeholders: Mapping[str, str]) -> str:
    """Return a translated string with its placeholders filled in.

    A translation can carry a brace that is not a placeholder, and a model is
    better off with the raw sentence than with nothing at all.
    """
    try:
        return template.format_map(_KeepUnknownPlaceholders(placeholders))
    except AttributeError, IndexError, KeyError, ValueError:
        return template


def _language(hass: HomeAssistant, llm_context: LLMContext) -> str:
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


def _first_sentence(text: str) -> str:
    """Return the first sentence, which is what a list of features needs."""
    sentence, period, _ = text.partition(". ")
    return f"{sentence}{period}".strip()


def _error(message: str) -> ToolResult:
    """Return a refusal or failure the model can read and pass on."""
    return ToolResult(data={"error": message}, error=True)


class _IssueStrings:
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
    ) -> _IssueStrings:
        """Load the issue translations for the language of the conversation."""
        language = _language(hass, llm_context)
        return cls(await async_get_translations(hass, language, "issues", {DOMAIN}))

    def _key(self, issue: ir.IssueEntry, path: str) -> str:
        """Return the translation key of a part of the issue."""
        return f"component.{DOMAIN}.issues.{_kind(issue)}.{path}"

    def render(
        self,
        issue: ir.IssueEntry,
        path: str,
        extra_placeholders: Mapping[str, str] | None = None,
    ) -> str | None:
        """Return a part of the issue, filled in, or None if it has no such part."""
        if (template := self._strings.get(self._key(issue, path))) is None:
            return None
        return _render(template, {**_placeholders(issue), **(extra_placeholders or {})})

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


def _kind(issue: ir.IssueEntry) -> str:
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
def _async_ghosts(hass: HomeAssistant) -> list[ir.IssueEntry]:
    """Return Spook's issues that are actually up, newest first.

    An issue that is not active is the empty record Home Assistant keeps to
    remember an ignore over a restart. Nobody can see it, so neither can this.
    """
    ghosts = [
        issue
        for (domain, _), issue in ir.async_get(hass).issues.items()
        if domain == DOMAIN and issue.active
    ]
    return sorted(ghosts, key=lambda issue: issue.created, reverse=True)


@callback
def _async_ghost(hass: HomeAssistant, issue_id: str) -> ir.IssueEntry | None:
    """Return one of Spook's issues that is up, by ID."""
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    if issue is None or not issue.active:
        return None
    return issue


def _unknown_ghost(issue_id: str) -> ToolResult:
    """Return the answer for an issue ID that is not one of Spook's."""
    return _error(
        f"There is no open Spook issue with the ID {issue_id!r}. "
        "Use spook__list_ghosts to see which ones there are."
    )


class _FixFlowUnavailableError(Exception):
    """A fix flow that could not even be started."""


@asynccontextmanager
async def _async_fix_flow(
    hass: HomeAssistant, issue: ir.IssueEntry
) -> AsyncIterator[tuple[RepairsFlowManager, RepairsFlowResult]]:
    """Start an issue's fix flow, and make sure it is gone afterwards.

    Through Home Assistant's own flow manager, so the flow runs exactly as it
    would from the dashboard, the checks it does before it deletes anything
    included.
    """
    if (manager := repairs_flow_manager(hass)) is None:
        msg = "Home Assistant's repairs are not set up."
        raise _FixFlowUnavailableError(msg)

    try:
        result = await manager.async_init(DOMAIN, context={"issue_id": issue.issue_id})
    except UnknownStep as err:
        raise _FixFlowUnavailableError(str(err)) from err

    try:
        yield manager, result
    finally:
        # A flow that ended is gone already. One that did not would hang
        # around waiting for an answer that is never coming.
        with suppress(UnknownFlow):
            manager.async_abort(result["flow_id"])


def _summary(issue: ir.IssueEntry, strings: _IssueStrings) -> JsonObjectType:
    """Return what every tool says about an issue, at the least."""
    return {
        "issue_id": issue.issue_id,
        "kind": _kind(issue),
        "title": strings.title(issue),
        "severity": str(issue.severity),
        "ignored": issue.dismissed_version is not None,
        "is_fixable": issue.is_fixable,
        "learn_more_url": issue.learn_more_url,
        "created": issue.created.isoformat(),
    }


class _SpookTool(Tool):
    """What every Spook tool shares: who may call it, and how."""

    integration = DOMAIN

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Refuse whoever is not an administrator, then do the work."""
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
            return _error(
                "Spook only changes repairs for a signed-in administrator, "
                "and this request has no user."
            )

        user = await hass.auth.async_get_user(user_id)
        if user is None or not user.is_admin:
            return _error("Spook's repairs are for administrators only.")

        return None

    @abstractmethod
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """Do what the tool does, with arguments that passed validation."""


class ListGhostsTool(_SpookTool):
    """List Spook's open repair issues."""

    name = "spook__list_ghosts"
    title = "List Spook's ghosts"
    description = (
        "List the open repair issues Spook raised: references to entities, "
        "actions, areas, devices and more that do not exist anymore, and "
        "leftovers like empty areas or unused labels. Newest first. Ignored "
        "ones are left out unless asked for."
    )
    annotations = _READ_ONLY
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
                    f"(default: {_DEFAULT_LIMIT}, max: {_MAX_LIMIT})."
                ),
                default=_DEFAULT_LIMIT,
            ): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=_MAX_LIMIT)
            ),
        }
    )

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """List the ghosts."""
        ghosts = [
            issue
            for issue in _async_ghosts(hass)
            if (args["include_ignored"] or issue.dismissed_version is None)
            and args.get("kind") in (None, _kind(issue))
        ]

        strings = await _IssueStrings.async_load(hass, llm_context)
        return ToolResult(
            data={
                "total": len(ghosts),
                "ghosts": [
                    _summary(issue, strings) for issue in ghosts[: args["limit"]]
                ],
            }
        )


class ExplainGhostTool(_SpookTool):
    """Explain one of Spook's repair issues."""

    name = "spook__explain_ghost"
    title = "Explain a Spook ghost"
    description = (
        "Explain one Spook repair issue: the full description people see in "
        "the Repairs dashboard, the fix options it offers, and the raw details "
        "Spook worked out, like likely renames of entities that went missing."
    )
    annotations = _READ_ONLY
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
        if (issue := _async_ghost(hass, args["issue_id"])) is None:
            return _unknown_ghost(args["issue_id"])

        strings = await _IssueStrings.async_load(hass, llm_context)
        data: JsonObjectType = {
            **_summary(issue, strings),
            "description": strings.description(issue),
            "fix_options": [],
            "placeholders": dict(issue.translation_placeholders or {}),
        }
        if issue.is_fixable:
            data.update(await self._async_fix_options(hass, issue, strings))

        return ToolResult(data=data)

    @staticmethod
    async def _async_fix_options(
        hass: HomeAssistant, issue: ir.IssueEntry, strings: _IssueStrings
    ) -> JsonObjectType:
        """Return what the fix offers right now, by asking the fix itself.

        The translations list every option a fix can have, not the ones it
        has today. A dashboard resource from YAML gets no menu at all, just a
        note saying where the file is, and a model reading the translations
        would offer a button that is not there.
        """
        try:
            async with _async_fix_flow(hass, issue) as (_, result):
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
        except _FixFlowUnavailableError as err:
            return {"fix_unavailable": str(err)}


class FindUsagesTool(_SpookTool):
    """Find where something is used."""

    name = "spook__find_usages"
    title = "Find where something is used"
    description = (
        "Find where an entity ID, an action (domain.action), or the ID of a "
        "label, area or floor is used: in automations, scripts, scenes, "
        "dashboards, groups, helpers and template helpers. Read the way "
        "Spook's repairs read them, templates included. Unlike the repairs, "
        "it also reports a reference in a disabled step, because that step "
        "breaks the day somebody switches it back on. Answers 'what breaks "
        "if I remove this' and 'where is this used'."
    )
    annotations = _READ_ONLY
    parameters = probatio.Schema(
        {
            probatio.Required(
                "reference",
                description=(
                    "What to look for, like 'light.kitchen', 'notify.mobile_app', "
                    "or the ID of a label, area or floor."
                ),
            ): probatio.All(
                str, probatio.Strip, probatio.Lower, probatio.Length(min=1)
            ),
            probatio.Optional(
                "kind",
                description=(
                    "What the reference is, if known. Without it, anything with "
                    "a dot is looked for as an entity and as an action, and "
                    "anything else as a label, area and floor."
                ),
            ): probatio.In(REFERENCE_TYPES),
            probatio.Optional(
                "limit",
                description=(
                    "Maximum number of places to return "
                    f"(default: {_DEFAULT_LIMIT}, max: {_MAX_LIMIT})."
                ),
                default=_DEFAULT_LIMIT,
            ): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=_MAX_LIMIT)
            ),
        }
    )

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """Find the usages."""
        reference: str = args["reference"]
        searched_as = (
            (args["kind"],) if "kind" in args else reference_types_for(reference)
        )
        usages = await async_find_usages(hass, reference, searched_as)

        return ToolResult(
            data={
                "reference": reference,
                "searched_as": list(searched_as),
                "total": len(usages),
                "usages": [usage.as_dict() for usage in usages[: args["limit"]]],
            }
        )


class _IgnoreToolBase(_SpookTool):
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
        if (issue := _async_ghost(hass, args["issue_id"])) is None:
            return _unknown_ghost(args["issue_id"])

        ir.async_ignore_issue(hass, DOMAIN, issue.issue_id, ignore=self.ignore)
        return ToolResult(data={"issue_id": issue.issue_id, "ignored": self.ignore})


class IgnoreGhostTool(_IgnoreToolBase):
    """Ignore one of Spook's issues."""

    name = "spook__ignore_ghost"
    title = "Ignore a Spook ghost"
    description = (
        "Ignore one Spook repair issue, the same as selecting ignore in the "
        "Repairs dashboard. Spook keeps quiet about it until it finds "
        "something new."
    )
    ignore = True


class UnignoreGhostTool(_IgnoreToolBase):
    """Stop ignoring one of Spook's issues."""

    name = "spook__unignore_ghost"
    title = "Stop ignoring a Spook ghost"
    description = "Stop ignoring one Spook repair issue, so it shows up again."
    ignore = False


class FixGhostTool(_SpookTool):
    """Run one fix option of an issue's fix flow."""

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
        if (issue := _async_ghost(hass, args["issue_id"])) is None:
            return _unknown_ghost(args["issue_id"])
        if not issue.is_fixable:
            return _error(f"The issue {issue.issue_id!r} has no fix to run.")

        strings = await _IssueStrings.async_load(hass, llm_context)

        try:
            async with _async_fix_flow(hass, issue) as (manager, started):
                if started["type"] is not FlowResultType.MENU:
                    return self._outcome(issue, started, strings)

                offered = list(started["menu_options"])
                if args["option"] not in offered:
                    return _error(
                        f"The fix for {issue.issue_id!r} does not offer "
                        f"{args['option']!r}. It offers: {', '.join(offered)}."
                    )

                finished = await manager.async_configure(
                    started["flow_id"], {"next_step_id": args["option"]}
                )
                return self._outcome(issue, finished, strings)
        except _FixFlowUnavailableError as err:
            return _error(str(err))

    def _outcome(
        self, issue: ir.IssueEntry, result: Any, strings: _IssueStrings
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

        return _error(
            "This fix asks for more than a choice from a menu. Open the issue "
            "in the Repairs dashboard to finish it."
        )


class CheckReferencesTool(_SpookTool):
    """Check a draft for references to things that do not exist."""

    name = "spook__check_references"
    title = "Check a draft for ghosts"
    description = (
        "Check a draft automation, script, scene or dashboard card before "
        "saving it, the way Spook's repairs would check it after: entities, "
        "actions, devices, areas, floors, labels, triggers and conditions "
        "that do not exist. Missing entities come with what Spook knows, like "
        "a likely rename. An empty result means the draft is clean."
    )
    annotations = _READ_ONLY
    parameters = probatio.Schema(
        {
            probatio.Required("kind", description="What the draft is."): probatio.In(
                DRAFT_KINDS
            ),
            probatio.Required(
                "config",
                description=(
                    "The draft, as the JSON object it would be saved as. A "
                    "dashboard can be a single card, a view or a whole dashboard."
                ),
            ): dict,
        }
    )

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """Check the draft."""
        try:
            unknown: dict[str, Any] = await async_check_draft(
                hass, args["kind"], args["config"]
            )
        except DraftError as err:
            return _error(str(err))

        if entities := unknown.get("entities"):
            unknown["entities"] = await async_describe_unknown_entities(hass, entities)

        return ToolResult(data={"clean": not unknown, "unknown": unknown})


class OverviewTool(_SpookTool):
    """Summarize how the house is doing, by Spook's count."""

    name = "spook__overview"
    title = "Spook's overview"
    description = (
        "A short summary of Spook's repair issues: how many are open and "
        "ignored per kind, and the oldest open ones. Start here for 'how is "
        "my house doing', then use spook__list_ghosts for the details."
    )
    annotations = _READ_ONLY

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """Count the ghosts."""
        ghosts = _async_ghosts(hass)
        strings = await _IssueStrings.async_load(hass, llm_context)

        kinds: dict[str, dict[str, Any]] = {}
        # Oldest first, so the title each kind is shown with is that of the
        # issue that has been waiting longest.
        for issue in reversed(ghosts):
            counts = kinds.setdefault(
                _kind(issue),
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
                        "kind": _kind(issue),
                        "title": strings.title(issue),
                        "created": issue.created.isoformat(),
                    }
                    for issue in still_open[::-1][:_OLDEST_IN_OVERVIEW]
                ],
            }
        )


class ListFeaturesTool(_SpookTool):
    """List the triggers, conditions and actions Spook adds."""

    name = "spook__list_features"
    title = "List what Spook adds"
    description = (
        "List the triggers, conditions and actions Spook adds to Home "
        "Assistant, for writing automations and scripts with them. Triggers "
        "and conditions are used as 'spook.<name>', actions by their full "
        "name. Each comes with its name and a one-line description."
    )
    annotations = _READ_ONLY
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "kind",
                description="Only list 'triggers', 'conditions' or 'actions'.",
            ): probatio.In(_FEATURE_KINDS),
        }
    )

    @override
    async def _async_run(
        self, hass: HomeAssistant, args: dict[str, Any], llm_context: LLMContext
    ) -> ToolResult:
        """List the features."""
        language = _language(hass, llm_context)
        wanted = (args["kind"],) if "kind" in args else _FEATURE_KINDS
        features: dict[str, list[dict[str, str]]] = {}

        if "triggers" in wanted:
            features["triggers"] = await self._async_described(
                hass, language, "triggers", await async_get_triggers(hass)
            )
        if "conditions" in wanted:
            features["conditions"] = await self._async_described(
                hass, language, "conditions", await async_get_conditions(hass)
            )
        if "actions" in wanted:
            features["actions"] = await self._async_actions(hass, language)

        return ToolResult(data=features)

    @staticmethod
    async def _async_described(
        hass: HomeAssistant, language: str, category: str, keys: Iterable[str]
    ) -> list[dict[str, str]]:
        """Return Spook's triggers or conditions, named the way they are used."""
        strings = await async_get_translations(hass, language, category, {DOMAIN})
        prefix = f"component.{DOMAIN}.{category}"
        return [
            {
                "name": f"{DOMAIN}.{key}",
                "title": strings.get(f"{prefix}.{key}.name", key),
                "description": _first_sentence(
                    strings.get(f"{prefix}.{key}.description", "")
                ),
            }
            for key in sorted(keys)
        ]

    @staticmethod
    async def _async_actions(
        hass: HomeAssistant, language: str
    ) -> list[dict[str, str]]:
        """Return the actions Spook has registered right now.

        Spook keeps them under one key per action, its own bare and those it
        adds to another integration as `<domain>_<action>`. Plenty of domains
        have an underscore in them, so rather than guess where the domain
        ends, each split is tried against what Home Assistant actually has.
        That also leaves out the actions of integrations that are not set up.
        """
        strings = await async_get_translations(hass, language, "services", {DOMAIN})
        prefix = f"component.{DOMAIN}.services."
        keys = {
            key.removeprefix(prefix).partition(".")[0]
            for key in strings
            if key.startswith(prefix)
        }

        actions: list[dict[str, str]] = []
        for key in sorted(keys):
            if (action := _registered_action(hass, key)) is None:
                continue
            actions.append(
                {
                    "name": action,
                    "title": strings.get(f"{prefix}{key}.name", action),
                    "description": _first_sentence(
                        strings.get(f"{prefix}{key}.description", "")
                    ),
                }
            )
        return actions


def _registered_action(hass: HomeAssistant, key: str) -> str | None:
    """Return the action behind a Spook services key, if it is registered."""
    if hass.services.has_service(DOMAIN, key):
        return f"{DOMAIN}.{key}"

    parts = key.split("_")
    for split in range(1, len(parts)):
        domain, service = "_".join(parts[:split]), "_".join(parts[split:])
        if hass.services.has_service(domain, service):
            return f"{domain}.{service}"

    return None


@callback
def async_get_spook_tools() -> LLMTools:
    """Return Spook's tools and the prompt that goes with them."""
    return LLMTools(
        tools=[
            OverviewTool(),
            ListGhostsTool(),
            ExplainGhostTool(),
            FindUsagesTool(),
            CheckReferencesTool(),
            ListFeaturesTool(),
            IgnoreGhostTool(),
            UnignoreGhostTool(),
            FixGhostTool(),
        ],
        prompt=PROMPT,
    )
