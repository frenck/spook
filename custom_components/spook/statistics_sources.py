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

    Having no state is not the same as being unknown, and three quite
    different things arrive looking identical.

    An entity that is registered and simply has no state right now is one whose
    integration has not finished setting up, or that somebody disabled. Home
    Assistant knows exactly what it is.

    An ID can carry long-term statistics without ever having been an entity.
    An integration publishing straight into the recorder has to name those
    after one, because `async_import_statistics` turns away anything that is
    not a valid entity ID, so a gas meter read by a service somewhere ends up
    as `sensor.something` with nothing behind it. The energy dashboard takes
    that and draws it. It is the opposite of unknown.

    And a deleted sensor leaves its statistics behind. That one is worth being
    told about, which is the whole reason this is careful.
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
    deleted = {entry.entity_id for entry in registry.deleted_entities.values()}

    for statistic_id, (_metadata_id, meta) in metadata.items():
        # Statistics a sensor wrote for itself carry no name of their own:
        # Home Assistant takes that from the entity. One that does carry a
        # name was put there by something that had to supply it, so something
        # is publishing this, whatever used to live at the name.
        if meta.get("name") is not None:
            known.add(statistic_id)
            continue

        # A registration that says "deleted" is Home Assistant remembering
        # there was an entity here. That is a reference to something somebody
        # removed, and worth saying.
        if statistic_id in deleted:
            continue

        # Nothing registered, nothing deleted, and statistics all the same.
        # Home Assistant keeps a deleted entity for a month and then forgets
        # it, so past that there is no telling this from something that was
        # never an entity at all. Saying "unknown" here would be claiming to
        # know what Home Assistant no longer does.
        known.add(statistic_id)

    return known
