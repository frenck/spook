"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.automation import automations_with_floor
from homeassistant.components.script import scripts_with_floor
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers import (
    area_registry as ar,
    floor_registry as fr,
)
from homeassistant.util import dt as dt_util

from ....const import LOGGER
from ....reference_extraction import async_collect_mentioned_strings
from ....repairs import AbstractSpookRepair

# Give a freshly created floor time to get areas assigned before nagging.
_MINIMUM_AGE = timedelta(days=1)


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds floors that hold no areas and are used nowhere.

    A floor exists to group areas. One with no areas, and no automation or
    script targeting it, is dead weight. Surfaced as tidiness, with a fix
    flow to remove it.
    """

    domain = "homeassistant"
    repair = "empty_floors"
    inspect_events = {
        EVENT_HOMEASSISTANT_STARTED,
        fr.EVENT_FLOOR_REGISTRY_UPDATED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
    }
    inspect_on_reload = True
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        mentioned = async_collect_mentioned_strings(self.hass)

        floor_registry = fr.async_get(self.hass)
        area_registry = ar.async_get(self.hass)

        cutoff = dt_util.utcnow() - _MINIMUM_AGE
        for floor in floor_registry.async_list_floors():
            self.possible_issue_ids.add(floor.floor_id)

            if floor.created_at > cutoff:
                # Just created; leave time to assign areas.
                continue
            if ar.async_entries_for_floor(area_registry, floor.floor_id):
                continue
            if automations_with_floor(self.hass, floor.floor_id):
                continue
            if scripts_with_floor(self.hass, floor.floor_id):
                continue
            if floor.floor_id in mentioned:
                # Named somewhere in an automation or script without
                # being a target of it. That is not proof it is in use: the
                # collector takes every string it finds and a coincidence
                # counts the same as a reference. It is enough to stop
                # offering to delete it, which is all this decides.
                continue

            self.async_create_issue(
                issue_id=floor.floor_id,
                is_fixable=True,
                data={"empty_floor_id": floor.floor_id, "floor": floor.name},
                translation_placeholders={"floor": floor.name},
            )
