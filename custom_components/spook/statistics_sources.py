"""Spook - Your homie. Telling a missing entity from one that never was."""

from __future__ import annotations

from datetime import timedelta
import functools
from typing import TYPE_CHECKING

from homeassistant.components.recorder.statistics import (
    get_metadata,
    validate_statistics,
)
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import DATA_INSTANCE, get_instance
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime
    from typing import Any

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant

# The recorder validation issue type for a statistic ID that has recorded
# statistics but no matching sensor state at all. Other issue types (unit or
# state-class changes, intentionally excluded entities) are either handled
# by Home Assistant itself or expected.
_ORPHAN_ISSUE_TYPE = "no_state"

# How long a statistic has to keep looking abandoned before Spook says so.
# Nothing here is urgent: statistics left behind by a sensor removed last
# year keep just as well for another quarter of an hour.
_SETTLING_TIME = timedelta(minutes=15)

# When each currently abandoned statistic was first seen that way. Held per
# instance rather than written down, so a restart starts every wait over,
# which is the point: the minutes after a start are when the house is least
# sure what it has.
DATA_ABANDONED_SINCE: HassKey[dict[str, datetime]] = HassKey(
    "spook_statistics_abandoned_since",
)


@callback
def async_setup_abandoned_statistics_watching(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Watch for anything being waited on turning up again.

    The wait exists so that a sensor briefly away is not mistaken for one
    that is gone, and the only way to be sure it stayed away is to be
    watching the whole time. Looking every few minutes is not that: a sensor
    can come back and go again between two looks, and both of them would see
    it missing with nothing in between to say otherwise. Its wait would carry
    on from before it returned, and what is on the end of that wait is Spook
    offering to delete its history.

    Whether a statistic has a state is worked out from the state machine, so
    a state change is the event that settles it. The entity registry raises
    its own, which the repair already listens to, and a sensor that never
    reaches the registry raises none of those at all.
    """

    @callback
    def _something_being_waited_on_is_back(event_data: Mapping[str, Any]) -> bool:
        """Return whether this is one of them, arriving."""
        return event_data.get("new_state") is not None and event_data[
            "entity_id"
        ] in hass.data.get(DATA_ABANDONED_SINCE, {})

    @callback
    def _start_its_wait_over(event: Event) -> None:
        """Forget how long it was away, because it is not away now."""
        hass.data[DATA_ABANDONED_SINCE].pop(event.data["entity_id"], None)

    return hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        _start_its_wait_over,
        event_filter=_something_being_waited_on_is_back,
    )


@callback
def _async_abandoned_since(hass: HomeAssistant) -> dict[str, datetime]:
    """Return when each abandoned statistic was first seen that way."""
    if DATA_ABANDONED_SINCE not in hass.data:
        hass.data[DATA_ABANDONED_SINCE] = {}
    return hass.data[DATA_ABANDONED_SINCE]


async def async_settled_orphaned_statistic_ids(hass: HomeAssistant) -> set[str]:
    """Return the statistics that have kept looking abandoned long enough.

    A sensor is briefly in neither the state machine nor the registry more
    often than it sounds: an integration re-registering its entities, a
    config entry reloading, the moments during a start before everything has
    arrived. Every one of those is a window in which a working sensor's
    history looks abandoned, and what is on offer here is deleting it. #1672.

    Asked by the report and by the fix, and it has to be the same question.
    A fix satisfied by one glance would delete the history of a sensor that
    came back days ago and happened to be between two of those windows when
    somebody pressed the button, which is the very thing the wait is for.
    """
    abandoned = await async_abandoned_statistic_ids(hass)

    now = dt_util.utcnow()
    since = _async_abandoned_since(hass)
    # Rebuilt rather than added to, so anything that turned up again drops
    # out and starts its wait from scratch if it goes missing later.
    since = hass.data[DATA_ABANDONED_SINCE] = {
        statistic_id: since.get(statistic_id, now) for statistic_id in abandoned
    }

    return {
        statistic_id
        for statistic_id, first_seen in since.items()
        if now - first_seen >= _SETTLING_TIME
    }


async def async_abandoned_statistic_ids(hass: HomeAssistant) -> set[str]:
    """Return the statistics with no entity of any kind behind them.

    In one place because two things ask it and they must not drift: the
    repair that reports them, and the fix that offers to clear them. A fix
    working from a different answer than the report would delete something
    nobody was shown.

    This is a snapshot of one moment and says nothing about how long it has
    looked this way, which is a judgement its callers make for themselves.
    """
    if DATA_INSTANCE not in hass.data:
        return set()  # Recorder is not set up.

    validation = await get_instance(hass).async_add_executor_job(
        validate_statistics,
        hass,
    )
    candidates = {
        statistic_id
        for statistic_id, issues in validation.items()
        if any(issue.type == _ORPHAN_ISSUE_TYPE for issue in issues)
    }

    # Having no state is not the same as being left behind. A registered
    # entity that is disabled or not set up yet has statistics waiting for it,
    # and an integration can publish statistics straight into the recorder
    # with no entity ever existing; the energy dashboard draws those perfectly
    # happily. Following the repair on either would delete working history.
    # #1625.
    return candidates - await async_known_to_home_assistant(hass, candidates)


async def async_known_to_home_assistant(
    hass: HomeAssistant,
    entity_ids: set[str],
) -> set[str]:
    """Return which of these Home Assistant knows about, state or no state.

    Having no state is not the same as being unknown, and two quite different
    things arrive looking identical.

    An entity that is registered and simply has no state right now is one whose
    integration has not finished setting up, or that somebody disabled. Home
    Assistant knows exactly what it is.

    And an ID can carry long-term statistics without ever having been an
    entity. An integration publishing straight into the recorder has to name
    those after one, because `async_import_statistics` turns away anything
    that is not a valid entity ID, so a gas meter read by a service somewhere
    ends up as `sensor.something` with nothing behind it. The energy dashboard
    takes that and draws it. It is the opposite of unknown.

    Which of those two a set of statistics is comes from the statistics
    themselves. A sensor writing its own carries no name: Home Assistant takes
    that from the entity, and the sensor recorder puts `None` there every
    time. Anything importing has to supply one, because the metadata demands
    the key. So a name is something having put these here on purpose.

    Deliberately not the entity registry's record of what was deleted, which
    was the first way this was written. Home Assistant only registers an
    entity that offers a unique ID, and throws away what it remembers about a
    deleted one after a month, so "no record of it" covers a sensor from a
    YAML template that never had one and a sensor removed last year. Reading
    that as "never was an entity" would quietly drop the reference this repair
    exists to point out.
    """
    if not entity_ids:
        return set()

    registry = er.async_get(hass)
    known = entity_ids & set(registry.entities)

    if not (rest := entity_ids - known) or DATA_INSTANCE not in hass.data:
        return known

    metadata = await get_instance(hass).async_add_executor_job(
        functools.partial(get_metadata, hass, statistic_ids=rest),
    )

    return known | {
        statistic_id
        for statistic_id, (_metadata_id, meta) in metadata.items()
        if meta.get("name") is not None
    }
