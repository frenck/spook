"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EntityCategory
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from ...entity import SpookEntityDescription
from .entity import RepairsSpookEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class RepairsSpookSensorEntityDescription(
    SpookEntityDescription,
    SensorEntityDescription,
):
    """Class describing Spook Repairs sensor entities."""

    value_fn: Callable[[list[ir.IssueEntry]], int]
    update_events: set[str] = field(default_factory=set)


SENSORS: tuple[RepairsSpookSensorEntityDescription, ...] = (
    RepairsSpookSensorEntityDescription(
        key="total_issues",
        translation_key="repairs_total_issues",
        entity_id="sensor.issues",
        icon="mdi:wrench",
        native_unit_of_measurement="issues",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED},
        value_fn=lambda items: len([item for item in items if item.active]),
    ),
    RepairsSpookSensorEntityDescription(
        key="active_issues",
        translation_key="repairs_active_issues",
        entity_id="sensor.active_issues",
        icon="mdi:wrench-check",
        native_unit_of_measurement="issues",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED},
        value_fn=lambda items: len(
            [item for item in items if item.active and not item.dismissed_version],
        ),
    ),
    RepairsSpookSensorEntityDescription(
        key="ignored_issues",
        translation_key="repairs_ignored_issues",
        entity_id="sensor.ignored_issues",
        icon="mdi:wrench-clock",
        native_unit_of_measurement="issues",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED},
        value_fn=lambda items: len(
            [item for item in items if item.active and item.dismissed_version],
        ),
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    _entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook sensor."""
    async_add_entities(
        HomeAssistantSpookSensorEntity(description) for description in SENSORS
    )


class HomeAssistantSpookSensorEntity(RepairsSpookEntity, SensorEntity):
    """Spook sensor providing repairs information."""

    entity_description: RepairsSpookSensorEntityDescription

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""

        @callback
        def _update_state(_: Event) -> None:
            """Update state."""
            self.async_schedule_update_ha_state()

        for event in self.entity_description.update_events:
            self.async_on_remove(self.hass.bus.async_listen(event, _update_state))

        self.async_on_remove(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _update_state),
        )

    @property
    def native_value(self) -> int:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            list(ir.async_get(self.hass).issues.values()),
        )
