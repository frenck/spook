"""Spook - Your homie. Telling a missing entity from one that never was."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from homeassistant.components.recorder.statistics import get_metadata
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import DATA_INSTANCE, get_instance

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


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
