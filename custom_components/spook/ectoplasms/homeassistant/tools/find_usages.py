"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers.llm import ToolResult

from ....llm_tools import DEFAULT_LIMIT, MAX_LIMIT, READ_ONLY, AbstractSpookTool
from ....usage_finding import REFERENCE_TYPES, async_find_usages, reference_types_for

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.llm import LLMContext


def _reference(value: str) -> str:
    """Return a reference to look for, without stray spaces or capitals.

    Done here and not with probatio's Strip and Lower. Once Home Assistant
    converts the schema for a model, those turn a plain string into an
    `allOf` with formats no JSON Schema knows.
    """
    return probatio.Length(min=1)(value.strip().lower())


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookTool):
    """Find where something is used."""

    domain = DOMAIN
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
    annotations = READ_ONLY
    parameters = probatio.Schema(
        {
            probatio.Required(
                "reference",
                description=(
                    "What to look for, like 'light.kitchen', 'notify.mobile_app', "
                    "or the ID of a label, area or floor."
                ),
            ): probatio.All(str, _reference),
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
