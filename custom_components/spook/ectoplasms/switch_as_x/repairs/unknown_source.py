"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....repairs import AbstractSpookEntityPlatformUnknownSourceRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityPlatformUnknownSourceRepair):
    """Spook repair tries to find unknown source entites for switch_as_x."""

    domain = "switch_as_x"
    repair = "switch_as_x_unknown_source"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = "switch_as_x"

    def _get_source_entity_id(self, entity: Any) -> str:
        """Return the wrapped switch's entity ID."""
        # pylint: disable-next=protected-access
        return entity._switch_entity_id  # noqa: SLF001
