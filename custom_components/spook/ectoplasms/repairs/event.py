"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.issue_registry import EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED

from ...entity import SpookEntityDescription
from .entity import RepairsSpookEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class RepairsSpookEventEntityDescription(
    SpookEntityDescription,
    EventEntityDescription,
):
    """Class describing Spook Repairs event entities."""


async def async_setup_entry(
    _hass: HomeAssistant,
    _entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook event."""
    async_add_entities(
        [
            RepairsSpookEventEntity(
                RepairsSpookEventEntityDescription(
                    key="event",
                    translation_key="repairs_event",
                    entity_id="event.repair",
                    event_types=["create", "remove", "update"],
                ),
            ),
        ],
    )


class RepairsSpookEventEntity(RepairsSpookEntity, EventEntity):
    """Spook sensor providing repairs information."""

    entity_description: RepairsSpookEventEntityDescription
    _attr_name = None

    async def async_added_to_hass(self) -> None:
        """Register for event updates."""

        @callback
        def _fire(event: Event) -> None:
            """Update state."""
            data = {**event.data}
            event_type = data.pop("action")
            self._trigger_event(event_type, data)
            self.async_schedule_update_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED, _fire),
        )
