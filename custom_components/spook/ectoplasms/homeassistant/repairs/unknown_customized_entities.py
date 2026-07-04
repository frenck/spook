"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core_config import DATA_CUSTOMIZE
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds customize entries for entities that do not exist.

    The `customize:` section can pin attributes on a specific entity. When
    that entity is renamed or removed, the customization becomes a dangling
    reference doing nothing. Only exact entity keys are checked; glob and
    domain customizations are patterns, not references.
    """

    domain = "homeassistant"
    repair = "unknown_customized_entities"
    inspect_events = {
        EVENT_HOMEASSISTANT_STARTED,
        EVENT_CORE_CONFIG_UPDATE,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        self.possible_issue_ids.add(self.repair)

        if not (customize := self.hass.data.get(DATA_CUSTOMIZE)):
            return  # No customizations at all.

        # `_exact` holds the per-entity customizations, keyed by entity ID.
        # Glob and domain customizations live separately and are patterns.
        # pylint: disable-next=protected-access
        exact = customize._exact  # noqa: SLF001
        if not exact:
            return

        if unknown := async_filter_known_entity_ids(
            self.hass,
            entity_ids=list(exact),
            known_entity_ids=async_get_all_entity_ids(self.hass),
        ):
            self.async_create_issue(
                issue_id=self.repair,
                translation_placeholders={
                    "entities": async_describe_unknown_entities(
                        self.hass, sorted(unknown)
                    ),
                },
            )
