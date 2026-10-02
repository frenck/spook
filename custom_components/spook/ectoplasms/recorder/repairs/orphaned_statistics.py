"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import DATA_INSTANCE

from ....const import DOMAIN, LOGGER
from ....repairs import AbstractSpookRepair
from ....statistics_sources import (
    async_keep_statistic_ids,
    async_kept_statistic_ids,
    async_settled_orphaned_statistic_ids,
    async_statistics_still_settling,
)


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds long-term statistics without a matching entity.

    Removing a sensor leaves its recorded statistics behind; Home
    Assistant keeps them but never points them out. This surfaces them so
    they can be cleaned up on the Settings > Tools > Statistics page, which
    is the only place Home Assistant offers to do it: `clear_statistics` is
    a websocket command that page calls, and not an action anybody can reach
    from the Actions tool. That page was called Developer Tools and sat in
    the sidebar until Home Assistant moved it in 2026.
    """

    domain = "recorder"
    repair = "orphaned_statistics"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }

    # A statistic has to keep looking abandoned to be reported, so something
    # has to come back and look again. Nothing fires an event when a sensor
    # finally turns up, and on a quiet system the next registry change can be
    # days away, which would leave a first sighting waiting that long for its
    # second.
    inspect_interval = timedelta(minutes=5)

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        if DATA_INSTANCE not in self.hass.data:
            return  # Recorder is not set up.

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        self.possible_issue_ids.add(self.repair)

        settled = await async_settled_orphaned_statistic_ids(self.hass)

        if not settled and async_statistics_still_settling(self.hass):
            # Right after a start everything is still being waited on, so
            # nothing is settled yet. That is not the same as everything
            # being fine, and clearing the issue now would throw away the
            # "ignore" written on it. Leave what is there until it is known.
            prefix = f"{self.repair}_"
            self.issue_ids.update(
                issue_id.removeprefix(prefix)
                for domain, issue_id in self.issue_registry.issues
                if domain == DOMAIN and issue_id.startswith(prefix)
            )
            return

        orphaned = sorted(settled - await async_kept_statistic_ids(self.hass))

        if orphaned and self.async_issue_is_ignored(self.repair, references=orphaned):
            # Somebody said to keep exactly these. Written down where it
            # outlasts the issue, because the next one more or less on the
            # list would be a new issue nobody has ignored.
            await async_keep_statistic_ids(self.hass, set(orphaned))
            return

        if orphaned:
            self.async_create_issue(
                issue_id=self.repair,
                references=orphaned,
                is_fixable=True,
                # Handed to the fix so it knows what was offered. It looks
                # again before clearing anything and keeps the two answers
                # in common, so nothing goes that somebody was not shown and
                # nothing goes that has since come back.
                data={"orphaned_statistic_ids": ",".join(orphaned)},
                translation_placeholders={
                    "statistics": "\n".join(
                        f"- `{statistic_id}`" for statistic_id in orphaned
                    ),
                },
            )
