"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.recorder.statistics import validate_statistics
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import DATA_INSTANCE, get_instance

from ....const import LOGGER
from ....repairs import AbstractSpookRepair

# The recorder validation issue type for a statistic ID that has recorded
# statistics but no matching sensor state at all: a genuine orphan. Other
# issue types (unit or state-class changes, intentionally excluded
# entities) are either handled by Home Assistant itself or expected.
_ORPHAN_ISSUE_TYPE = "no_state"


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds long-term statistics without a matching entity.

    Removing a sensor leaves its recorded statistics behind; Home
    Assistant keeps them but never points them out. This surfaces them so
    they can be cleaned up on the Developer Tools > Statistics page, which
    is the only place Home Assistant offers to do it: `clear_statistics` is
    a websocket command that page calls, and not an action anybody can
    reach from Developer Tools > Actions.
    """

    domain = "recorder"
    repair = "orphaned_statistics"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        if DATA_INSTANCE not in self.hass.data:
            return  # Recorder is not set up.

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        self.possible_issue_ids.add(self.repair)

        validation = await get_instance(self.hass).async_add_executor_job(
            validate_statistics,
            self.hass,
        )
        orphaned = sorted(
            statistic_id
            for statistic_id, issues in validation.items()
            if any(issue.type == _ORPHAN_ISSUE_TYPE for issue in issues)
        )

        if orphaned:
            self.async_create_issue(
                issue_id=self.repair,
                translation_placeholders={
                    "statistics": "\n".join(
                        f"- `{statistic_id}`" for statistic_id in orphaned
                    ),
                },
            )
