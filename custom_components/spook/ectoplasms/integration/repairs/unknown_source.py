"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import sensor
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....repairs import AbstractSpookEntityPlatformUnknownSourceRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityPlatformUnknownSourceRepair):
    """Spook repair tries to find unknown source entities for integration."""

    domain = "integration"
    repair = "integration_unknown_source"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = "integration"

    source_platform_domain = sensor.DOMAIN

    def _get_source_entity_id(self, entity: Any) -> str:
        """Return the integrating sensor's source entity ID."""
        # pylint: disable-next=protected-access
        return entity._sensor_source_id  # noqa: SLF001
