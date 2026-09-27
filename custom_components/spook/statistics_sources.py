"""Spook - Your homie. Telling a missing entity from one that never was."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from homeassistant.components.recorder.statistics import (
    get_metadata,
    validate_statistics,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import DATA_INSTANCE, get_instance

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# The recorder validation issue type for a statistic ID that has recorded
# statistics but no matching sensor state at all. Other issue types (unit or
# state-class changes, intentionally excluded entities) are either handled
# by Home Assistant itself or expected.
_ORPHAN_ISSUE_TYPE = "no_state"


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
