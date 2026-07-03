"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.energy.validate import async_validate
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair

# The energy validation issue type raised when a referenced entity or
# statistic has no state at all: it was removed. Other issue types
# (unavailable, non-numeric, undefined statistics) are transient or are
# configuration choices rather than stale references.
_MISSING_ISSUE_TYPE = "entity_not_defined"


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds unknown entities referenced in the energy dashboard.

    Home Assistant validates the energy preferences but only surfaces the
    result inside the energy configuration panel; a removed entity left in
    the energy dashboard otherwise goes unnoticed.
    """

    domain = "energy"
    repair = "energy_unknown_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        if "energy" not in self.hass.config.components:
            return  # Energy dashboard is not set up.

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        self.possible_issue_ids.add(self.repair)

        validation = await async_validate(self.hass)
        unknown: set[str] = set()
        for issues_group in (
            validation.energy_sources,
            validation.device_consumption,
            validation.device_consumption_water,
        ):
            for issues in issues_group:
                if (issue := issues.issues.get(_MISSING_ISSUE_TYPE)) is not None:
                    unknown.update(
                        affected for affected, _detail in issue.affected_entities
                    )

        if unknown:
            self.async_create_issue(
                issue_id=self.repair,
                translation_placeholders={
                    "entities": async_describe_unknown_entities(
                        self.hass, sorted(unknown)
                    ),
                },
            )
