"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant.helpers.llm import ToolResult
from homeassistant.helpers.translation import async_get_translations

from ....condition import async_get_conditions
from ....const import DOMAIN
from ....llm_tools import (
    READ_ONLY,
    AbstractSpookTool,
    conversation_language,
    first_sentence,
)
from ....trigger import async_get_triggers

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.llm import LLMContext

_FEATURE_KINDS = ("triggers", "conditions", "actions")


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


# A tool does one thing, so it has one method to show.
# pylint: disable-next=too-few-public-methods
class SpookTool(AbstractSpookTool):
    """List the triggers, conditions and actions Spook adds."""

    domain = DOMAIN
    in_front = True
    name = "spook__list_features"
    title = "List what Spook adds"
    description = (
        "List the triggers, conditions and actions Spook adds to Home "
        "Assistant, for writing automations and scripts with them. Triggers "
        "and conditions are used as 'spook.<name>', actions by their full "
        "name. Each comes with its name and a one-line description."
    )
    annotations = READ_ONLY
    prompt_hint = (
        "Use spook__list_features for the triggers, conditions and actions Spook adds."
    )
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
        language = conversation_language(hass, llm_context)
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
                "description": first_sentence(
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
                    "description": first_sentence(
                        strings.get(f"{prefix}{key}.description", "")
                    ),
                }
            )
        return actions
