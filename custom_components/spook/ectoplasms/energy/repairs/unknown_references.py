"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....energy_preferences import async_unknown_energy_entities
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds unknown entities referenced in the energy dashboard.

    Home Assistant validates the energy preferences but only surfaces the
    result inside the energy configuration panel; a removed entity left in
    the energy dashboard otherwise goes unnoticed.
    """

    domain = "energy"
    repair = "energy_unknown_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }

    # Whether a source counts as known now depends on what the recorder holds,
    # and statistics arriving or being cleared raises no event at all. Without
    # a clock, an issue raised before the first import would sit there until
    # some unrelated registry change happened along, which on a quiet system
    # can be a long time.
    inspect_interval = timedelta(hours=1)

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        if "energy" not in self.hass.config.components:
            return  # Energy dashboard is not set up.

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        self.possible_issue_ids.add(self.repair)

        if unknown := await async_unknown_energy_entities(self.hass):
            entities = await async_describe_unknown_entities(self.hass, sorted(unknown))
            self.async_create_issue(
                issue_id=self.repair,
                references=unknown,
                is_fixable=True,
                data={
                    "energy_unknown_entity_ids": ",".join(sorted(unknown)),
                    "entities": entities,
                },
                translation_placeholders={"entities": entities},
            )
