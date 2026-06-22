"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import binary_sensor
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....repairs import AbstractSpookEntityPlatformUnknownSourceRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityPlatformUnknownSourceRepair):
    """Spook repair tries to find unknown source entities for trend sensors."""

    domain = "trend"
    repair = "trend_unknown_source"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_on_reload = "trend"

    source_platform_domain = binary_sensor.DOMAIN

    def _get_source_entity_id(self, entity: Any) -> str:
        """Return the trend sensor's source entity ID."""
        # pylint: disable-next=protected-access
        return entity._entity_id  # noqa: SLF001
