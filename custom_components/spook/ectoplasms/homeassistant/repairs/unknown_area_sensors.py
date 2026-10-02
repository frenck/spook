"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers import area_registry as ar, entity_registry as er

from ....const import LOGGER
from ....entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair

# The area settings that name a sensor, and how the issue calls each one.
AREA_SENSOR_FIELDS = {
    "temperature_entity_id": "temperature",
    "humidity_entity_id": "humidity",
}


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds areas whose temperature or humidity sensor is gone.

    Home Assistant checks the sensor when it is picked, and never again.
    Remove or rename it afterwards and the area keeps pointing at nothing,
    so Assist and area cards quietly lose the reading. Checked against the
    registry and the state machine, like every other unknown reference, and
    only once Home Assistant has started, so a sensor still loading is not
    mistaken for a missing one.
    """

    domain = "homeassistant"
    repair = "unknown_area_sensors"
    inspect_events = {
        EVENT_HOMEASSISTANT_STARTED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass)

        for area in ar.async_get(self.hass).async_list_areas():
            self.possible_issue_ids.add(area.id)

            unknown = {
                field: entity_id
                for field in AREA_SENSOR_FIELDS
                if (entity_id := getattr(area, field))
                and async_filter_known_entity_ids(
                    self.hass, [entity_id], known_entity_ids=known_entity_ids
                )
            }
            if not unknown:
                continue

            placeholders = {
                "area": area.name,
                "sensors": " and ".join(AREA_SENSOR_FIELDS[field] for field in unknown),
                "entities": async_describe_unknown_entities(
                    self.hass, sorted(unknown.values())
                ),
            }
            self.async_create_issue(
                issue_id=area.id,
                is_fixable=True,
                # Which setting points at the entity is part of the finding:
                # the same entity dangling from the other setting is a new
                # problem, not one somebody already chose to ignore.
                references={
                    f"{field}:{entity_id}" for field, entity_id in unknown.items()
                },
                # The fix flow is handed the data, not the placeholders, and
                # names the same things in its menu. It clears only the
                # settings listed here, the ones the user was shown.
                data={
                    "area_sensors_area_id": area.id,
                    "area_sensors_references": ",".join(
                        f"{field}:{entity_id}" for field, entity_id in unknown.items()
                    ),
                    **placeholders,
                },
                translation_placeholders=placeholders,
            )
