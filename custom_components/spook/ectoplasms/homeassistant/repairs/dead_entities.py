"""Spook - Your homie."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_RESTORED,
    EVENT_COMPONENT_LOADED,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import Integration, async_get_integrations
from homeassistant.util import dt as dt_util

from ....const import LOGGER
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from homeassistant.core import Event, State


# How long an integration gets to produce its first entity before Spook takes
# the silence at face value. Devices that push on their own schedule are the
# slow ones here: a weather station reporting every fifteen minutes is normal,
# and being wrong about this is worse than being late.
_LONG_ENOUGH_TO_PUSH = timedelta(hours=1)


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds registered entities that no longer exist.

    A registry entry whose integration loaded but never provided the
    entity this session gets a restored ``unavailable`` state. Grouped per
    config entry, and only for config entries that finished loading, so a
    slow or retrying integration is never mistaken for a dead entity.
    """

    domain = "homeassistant"
    repair = "dead_entities"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    automatically_clean_up_issues = True

    # Nothing happens when the wait below runs out: that is the whole point of
    # it, an integration that has gone quiet. So the passage of time has to be
    # what brings this back round.
    inspect_interval = _LONG_ENOUGH_TO_PUSH

    async def async_activate(self) -> None:
        """Handle activating the repair."""
        await super().async_activate()

        # The restored placeholder state can appear and disappear without
        # anything else saying so. An entity removed while its registry entry
        # survives gets one written for it, and an entity that finally shows
        # up overwrites the one it had. Neither touches the entity registry,
        # and the config entry stays loaded throughout, so the events above
        # only catch this at startup or by coincidence.
        #
        # Watched by the restored flag flipping rather than by entities being
        # added or removed: crossing into or out of that placeholder is the
        # entire signal this repair reads, and it is not something an ordinary
        # state change does.
        @callback
        def _restored_flag_changed(event_data: Mapping[str, Any]) -> bool:
            """Return if an entity entered or left the restored state."""

            def is_restored(state: State | None) -> bool:
                return bool(state and state.attributes.get(ATTR_RESTORED))

            return is_restored(event_data.get("old_state")) != is_restored(
                event_data.get("new_state")
            )

        @callback
        def _async_call_inspect_debouncer(_: Event) -> None:
            """Trigger an inspection when the restored flag flips."""
            self.inspect_debouncer.async_schedule_call()

        self._event_subs.add(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                _async_call_inspect_debouncer,
                event_filter=_restored_flag_changed,
            ),
        )

    @callback
    def _async_had_its_chance(
        self,
        entry_id: str,
        entity_registry: er.EntityRegistry,
    ) -> bool:
        """Return whether this config entry has had time to produce anything.

        Being loaded is not the same as having data. An integration fed by a
        webhook, Ecowitt among them, sets up in a moment and then waits for
        the device to push, which can be minutes. Everything it registered
        sits there restored and unavailable in the meantime, and reporting
        that would be telling somebody their weather station is gone while it
        is simply between readings.

        One entity that made it settles it at once: the data arrived, and
        whatever is still missing is missing for another reason. Failing that,
        the wait below, because an integration whose every entity is genuinely
        gone would otherwise never be reported at all.
        """
        newest: datetime | None = None

        for entry in er.async_entries_for_config_entry(entity_registry, entry_id):
            if (state := self.hass.states.get(entry.entity_id)) is None:
                continue

            if not state.attributes.get(ATTR_RESTORED):
                return True

            if newest is None or state.last_changed > newest:
                newest = state.last_changed

        # Read off the placeholders themselves rather than kept in the repair,
        # because a reload takes them away and writes them again, so this
        # starts over exactly when the integration does. Which is the point:
        # after a reload a push-fed integration has not been pushed to yet.
        return newest is not None and dt_util.utcnow() - newest >= _LONG_ENOUGH_TO_PUSH

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        entity_registry = er.async_get(self.hass)

        dead_by_entry: dict[str, list[str]] = defaultdict(list)
        for state in self.hass.states.async_all():
            if state.state != STATE_UNAVAILABLE or not state.attributes.get(
                ATTR_RESTORED
            ):
                continue
            entry = entity_registry.async_get(state.entity_id)
            if entry is None or entry.config_entry_id is None:
                # Only config-entry-backed entities can be confirmed dead by
                # cross-checking their config entry's load state.
                continue
            dead_by_entry[entry.config_entry_id].append(state.entity_id)

        entries = {
            entry_id: entry
            for entry_id in dead_by_entry
            if (entry := self.hass.config_entries.async_get_entry(entry_id)) is not None
            and entry.state is ConfigEntryState.LOADED
            and self._async_had_its_chance(entry_id, entity_registry)
        }

        # The name people know an integration by lives in its manifest. A
        # config entry's title is whatever it was set up as, which for an
        # account-based integration is the name of the account holder: being
        # told that "Franck Nijhof" registered dead entities is not helpful.
        names = await async_get_integrations(
            self.hass, {entry.domain for entry in entries.values()}
        )

        for entry_id, config_entry in entries.items():
            integration = names.get(config_entry.domain)
            name = (
                integration.name
                if isinstance(integration, Integration)
                else config_entry.domain
            )

            self.possible_issue_ids.add(entry_id)
            self.async_create_issue(
                issue_id=entry_id,
                issue_domain=config_entry.domain,
                is_fixable=True,
                data={
                    "dead_entities_config_entry_id": entry_id,
                    "integration": name,
                    "entities": "\n".join(
                        f"- `{entity_id}`"
                        for entity_id in sorted(dead_by_entry[entry_id])
                    ),
                },
                translation_placeholders={
                    "integration": name,
                    "entities": "\n".join(
                        f"- `{entity_id}`"
                        for entity_id in sorted(dead_by_entry[entry_id])
                    ),
                },
            )
