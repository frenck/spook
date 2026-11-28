"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers.llm import ToolResult

from ....draft_checking import (
    DRAFT_KINDS,
    DraftError,
    async_check_draft,
    async_describe_unknown_entities,
)
from ....llm_tools import (
    READ_ONLY,
    AbstractSpookTool,
    NotAJsonObjectError,
    error,
    unwrap_gemini_object,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.llm import LLMContext


def _draft_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return the draft to check, also when it came in as a JSON string.

    Read as Gemini wraps it, a draft names nothing, and nothing is clean.
    """
    try:
        return unwrap_gemini_object(config)
    except NotAJsonObjectError as err:
        message = "The draft should be a JSON object."
        raise DraftError(message) from err
    except ValueError as err:
        message = f"The draft is not valid JSON: {err}"
        raise DraftError(message) from err


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookTool):
    """Check a draft for references to things that do not exist."""

    domain = DOMAIN
    in_front = True
    name = "spook__check_references"
    title = "Check a draft for ghosts"
    description = (
        "Check a draft automation, script, scene or dashboard card before "
        "saving it, the way Spook's repairs would check it after: entities, "
        "actions, devices, areas, floors, labels, triggers, conditions and "
        "integration entries that do not exist, users that were removed, "
        "attributes an entity never has, and states an entity is never in, "
        "or values its attributes never have. Missing entities come with what "
        "Spook knows, like a likely rename, and the rest with the one most "
        "likely meant. A field that takes an entity ID but holds something "
        "that is not one is listed under not_entity_ids. An empty result "
        "means the draft is clean."
    )
    annotations = READ_ONLY
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
                hass, args["kind"], _draft_config(args["config"])
            )
        except DraftError as err:
            return error(str(err))

        if entities := unknown.get("entities"):
            unknown["entities"] = await async_describe_unknown_entities(hass, entities)

        return ToolResult(data={"clean": not unknown, "unknown": unknown})
