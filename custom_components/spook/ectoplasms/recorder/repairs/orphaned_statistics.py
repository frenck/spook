"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import DATA_INSTANCE
from homeassistant.util import dt as dt_util

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....statistics_sources import async_abandoned_statistic_ids

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

# How long a statistic has to keep looking abandoned before Spook says so.
# Nothing here is urgent: statistics left behind by a sensor removed last
# year keep just as well for another quarter of an hour.
_SETTLING_TIME = timedelta(minutes=15)


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

    _first_seen_abandoned: dict[str, datetime]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self._first_seen_abandoned = {}

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        if DATA_INSTANCE not in self.hass.data:
            return  # Recorder is not set up.

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        self.possible_issue_ids.add(self.repair)

        abandoned = await async_abandoned_statistic_ids(self.hass)

        # Reported only once it has looked this way for a while. A sensor is
        # briefly in neither the state machine nor the registry more often
        # than it sounds: an integration re-registering its entities, a
        # config entry being reloaded, the moments during a start before
        # everything has arrived. Every one of those is a window in which a
        # working sensor's history looks abandoned, and what this repair
        # offers to do about that is delete it. #1672.
        #
        # Kept in memory rather than written down, so a restart starts the
        # wait over. That is the point: the minutes after a start are exactly
        # when the house is least sure what it has.
        now = dt_util.utcnow()
        self._first_seen_abandoned = {
            statistic_id: self._first_seen_abandoned.get(statistic_id, now)
            for statistic_id in abandoned
        }

        orphaned = sorted(
            statistic_id
            for statistic_id, since in self._first_seen_abandoned.items()
            if now - since >= _SETTLING_TIME
        )

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
