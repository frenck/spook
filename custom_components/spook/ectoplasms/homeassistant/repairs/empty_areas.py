"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util

from ....const import LOGGER
from ....reference_extraction import async_collect_mentioned_strings
from ....registry_usage import async_area_in_use
from ....repairs import AbstractSpookRepair

# Give a freshly created area time to be filled before nagging about it.
# Creating an area and assigning devices to it is not instantaneous.
_MINIMUM_AGE = timedelta(days=1)


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds areas that hold nothing and are used nowhere.

    An area with no devices, no entities, and no automation or script
    targeting it is dead weight. Surfaced as tidiness, with a fix flow to
    remove it. References are checked so an area deliberately targeted by
    an automation or script is left alone.
    """

    domain = "homeassistant"
    repair = "empty_areas"
    inspect_events = {
        EVENT_HOMEASSISTANT_STARTED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
        dr.EVENT_DEVICE_REGISTRY_UPDATED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_on_reload = True
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        mentioned = async_collect_mentioned_strings(self.hass)

        area_registry = ar.async_get(self.hass)

        cutoff = dt_util.utcnow() - _MINIMUM_AGE
        for area in area_registry.async_list_areas():
            self.possible_issue_ids.add(area.id)

            if area.created_at > cutoff:
                # Just created; leave time to assign devices and entities.
                continue
            if async_area_in_use(self.hass, area.id, mentioned):
                continue

            self.async_create_issue(
                issue_id=area.id,
                is_fixable=True,
                data={"empty_area_id": area.id, "area": area.name},
                translation_placeholders={"area": area.name},
            )
