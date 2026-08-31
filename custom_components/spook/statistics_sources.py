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

    What is left over really is unknown: no registration, deleted or
    otherwise, and nothing recorded under the name. A registration that says
    "deleted" is left out on purpose, because that is a reference to something
    somebody removed, which is worth being told about.
    """
    if not entity_ids:
        return set()

    registry = er.async_get(hass)
    registered = entity_ids & set(registry.entities)

    if not (rest := entity_ids - registered) or DATA_INSTANCE not in hass.data:
        return registered

    # Never registered at all. Anything the recorder keeps under that name was
    # put there by something that is still doing it.
    never_registered = rest - {
        deleted.entity_id for deleted in registry.deleted_entities.values()
    }
    if not never_registered:
        return registered

    metadata = await get_instance(hass).async_add_executor_job(
        functools.partial(get_metadata, hass, statistic_ids=never_registered),
    )

    return registered | set(metadata)
