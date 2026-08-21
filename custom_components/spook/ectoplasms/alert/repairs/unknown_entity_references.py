"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.alert.const import DOMAIN
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_STATE_CHANGED
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair
from ..configuration import async_get_alert_configurations

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import Event, HomeAssistant


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds alerts watching an entity that is gone.

    An alert fires when the entity it watches enters a state. When that
    entity is renamed or removed, the alert keeps watching a name nothing
    answers to, so it can never fire again. Home Assistant does not check
    this, and an alert that never fires looks exactly like an alert with
    nothing to report.
    """

    domain = DOMAIN
    repair = "alert_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_on_reload = True
    automatically_clean_up_issues = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self._watched_entity_ids: set[str] = set()

    async def async_activate(self) -> None:
        """Handle activating the repair."""
        await super().async_activate()

        # An alert can watch a state-only entity, which comes and goes without
        # the entity registry hearing about it. Registry events alone would
        # miss both the moment it breaks and the moment it recovers.
        #
        # Narrowed to the entities some alert actually watches, because an
        # inspection here re-reads the configuration from disk. The sibling
        # repairs filter on add/remove alone, but they only walk objects
        # already in memory. The set comes from the last inspection, so a
        # newly watched entity is picked up by the reload that introduced it.
        @callback
        def _watched_entity_changed(event_data: Mapping[str, Any]) -> bool:
            """Return if a watched state entity was added or removed."""
            return event_data.get("entity_id") in self._watched_entity_ids and (
                event_data.get("old_state") is None
                or event_data.get("new_state") is None
            )

        @callback
        def _async_call_inspect_debouncer(_: Event) -> None:
            """Trigger an inspection when a watched entity appears or goes."""
            self.inspect_debouncer.async_schedule_call()

        self._event_subs.add(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                _async_call_inspect_debouncer,
                event_filter=_watched_entity_changed,
            ),
        )

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        entity_registry = er.async_get(self.hass)

        alerts = await async_get_alert_configurations(self.hass)
        self._watched_entity_ids = {
            alert.watched_entity_id
            for alert in alerts
            if alert.watched_entity_id is not None
        }

        for alert in alerts:
            self.possible_issue_ids.add(alert.entity_id)

            watched = alert.watched_entity_id
            if not watched:
                continue

            # Checked against the registry and the states, not the shared
            # entity filtering: an alert can legitimately watch a state-only
            # entity, or one in a domain that filtering ignores wholesale.
            if (
                entity_registry.async_get(watched) is not None
                or self.hass.states.get(watched) is not None
            ):
                continue

            self.async_create_issue(
                issue_id=alert.entity_id,
                translation_placeholders={
                    "alert": alert.name,
                    "entity_id": alert.entity_id,
                    "entities": async_describe_unknown_entities(self.hass, [watched]),
                },
            )
            LOGGER.debug(
                "Spook found alert %s watching unknown entity %s "
                "and created an issue for it",
                alert.entity_id,
                watched,
            )
