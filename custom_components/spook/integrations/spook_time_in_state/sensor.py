"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.start import async_at_start
from homeassistant.util import dt as dt_util

from .const import ATTR_OBSERVED, ATTR_SOURCE_STATE, CONF_STATES

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Not a state at all, only the source being away for a moment: an integration
# reloading, a device dropping off the network. Read as a change, a door that
# stayed shut all day would have its clock start over on every hiccup.
_NOT_A_STATE = (STATE_UNAVAILABLE, STATE_UNKNOWN)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize time in state config entry."""
    async_add_entities([TimeInStateSensor(hass, config_entry)])


class TimeInStateSensor(SensorEntity, RestoreEntity):  # pylint: disable=too-many-instance-attributes
    """Since when the source has been in its state, or last became one.

    A moment rather than a duration that counts up. The frontend shows a
    timestamp as "5 minutes ago" and keeps it current by itself, so this only
    writes when something actually changes, instead of every second for the
    recorder to keep.

    It keeps its moment across a restart, unlike the source's own last
    changed, which every start resets. And a source that is unavailable for a
    moment is not counted as a change at all.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        source = config_entry.options[CONF_ENTITY_ID]
        registry = er.async_get(hass)
        self._source = er.async_resolve_entity_id(registry, source) or source
        self._states = set(config_entry.options.get(CONF_STATES) or ())

        self._attr_name = config_entry.title
        self._attr_unique_id = config_entry.entry_id

        if (
            (source_entry := registry.async_get(self._source))
            and source_entry.device_id
            and (device := dr.async_get(hass).async_get(source_entry.device_id))
        ):
            self.device_entry = device

        self._since: datetime | None = None
        self._source_state: str | None = None
        self._observed = False

    @property
    def native_value(self) -> datetime | None:
        """Return since when."""
        return self._since

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the source, its state, and whether the change was seen.

        `observed` says the moment is when the change happened. Without it,
        the change happened while nobody was looking, Home Assistant being
        down for one, and the moment is when it was first noticed: the real
        one is earlier, or the same.
        """
        return {
            ATTR_ENTITY_ID: self._source,
            ATTR_SOURCE_STATE: self._source_state,
            ATTR_OBSERVED: self._observed,
        }

    async def async_added_to_hass(self) -> None:
        """Pick up where the last run left off, and start following."""
        await super().async_added_to_hass()

        if (last := await self.async_get_last_state()) is not None and (
            since := dt_util.parse_datetime(last.state)
        ) is not None:
            self._since = since
            self._source_state = last.attributes.get(ATTR_SOURCE_STATE)
            self._observed = bool(last.attributes.get(ATTR_OBSERVED))

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._source, self._async_source_changed
            )
        )

        @callback
        def _async_started(_: HomeAssistant) -> None:
            """Compare what was kept with what the source says now."""
            self._async_take(self.hass.states.get(self._source), observed=False)

        self.async_on_remove(async_at_start(self.hass, _async_started))

    @callback
    def _async_source_changed(self, event: Event[EventStateChangedData]) -> None:
        """Follow the source into its new state.

        Only seen happening when it came from a state. Arriving from nowhere,
        or back from being unavailable, it may well have changed somewhere in
        between, and the moment of arriving is not when.
        """
        old_state = event.data["old_state"]
        self._async_take(
            event.data["new_state"],
            observed=old_state is not None and old_state.state not in _NOT_A_STATE,
        )

    @callback
    def _async_take(self, state: State | None, *, observed: bool) -> None:
        """Take in the source's state, if it is one, and different."""
        if state is None or state.state in _NOT_A_STATE:
            return

        # The same as before: only its attributes changed, it came back from a
        # moment away, or it is still where it was before a restart.
        if state.state == self._source_state:
            return

        self._source_state = state.state
        if not self._states or state.state in self._states:
            self._since = state.last_changed
            self._observed = observed

        self.async_write_ha_state()
