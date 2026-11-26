"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import group
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_RESTORED,
    EVENT_COMPONENT_LOADED,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids
from ....entity_suggestions import async_describe_unknown_entities
from ....helper_sources import async_group_members
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import Event, HomeAssistant, State


def _members_of(state: State | None) -> list[Any] | tuple[Any, ...] | None:
    """Return the members a group's state lists, if it lists any.

    A list, or a tuple for the old `group.` ones. Other entities can have an
    `entity_id` of a single one, like a helper naming its source, and that
    is no list of members.
    """
    if state is None:
        return None

    members = state.attributes.get(ATTR_ENTITY_ID)
    return members if isinstance(members, (list, tuple)) else None


def _restored(state: State | None) -> bool:
    """Return whether a state is the one Home Assistant keeps while away."""
    return state is not None and state.attributes.get(ATTR_RESTORED) is True


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown member entities in groups."""

    domain = group.DOMAIN
    repair = "group_unknown_members"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = group.DOMAIN
    # A member can be state-only, set by a template or a script without a
    # unique ID, coming and going without the entity registry hearing.
    inspect_on_entity_added_or_removed = True

    automatically_clean_up_issues = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self._group_entity_ids: set[str] = set()

    async def async_activate(self) -> None:
        """Look again once a group lists other members.

        Every kind of group lists its members in its state, the old `group.`
        ones and the light, switch, sensor and other groups alike. A reload,
        an edit in the UI or `group.set` leaves the group with members it
        did not have, and it writes them down once it has. The reload being
        called comes before anything was reloaded.

        Only when both states list members, though. A group that is
        unavailable lists nothing: what an unavailable entity writes leaves
        its extra attributes out. One losing or regaining its members' states
        that way is no change to what it is made of, and a group with every
        member gone is exactly that. A reload still shows, for one in the
        entity registry: it waits the reload out in the state Home Assistant
        keeps for it while it is away. That is looked for on the groups the
        last look found. A new one comes with an entity registry entry, or
        as a state where there was none.
        """
        await super().async_activate()

        @callback
        def _members_changed(event_data: Mapping[str, Any]) -> bool:
            """Return if a group now lists other members, or reloaded."""
            old_state = event_data.get("old_state")
            new_state = event_data.get("new_state")
            old_members = _members_of(old_state)
            new_members = _members_of(new_state)
            if (
                old_members is not None
                and new_members is not None
                and old_members != new_members
            ):
                return True

            return event_data.get("entity_id") in self._group_entity_ids and (
                _restored(old_state) or _restored(new_state)
            )

        @callback
        def _look_again(_: Event) -> None:
            self.inspect_debouncer.async_schedule_call()

        self._event_subs.add(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED, _look_again, event_filter=_members_changed
            )
        )

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass)
        groups = list(async_group_members(self.hass))
        # Added to, never replaced: a group being reloaded is missing from its
        # platform until it is back, and a look in between would forget it
        # right before it returns. One that is gone for good sends nothing.
        self._group_entity_ids |= {entity.entity_id for entity, _ in groups}

        for entity, members in groups:
            self.possible_issue_ids.add(entity.entity_id)

            if unknown_entities := async_filter_known_entity_ids(
                self.hass, entity_ids=members, known_entity_ids=known_entity_ids
            ):
                described = await async_describe_unknown_entities(
                    self.hass,
                    sorted(unknown_entities),
                    referenced_by={entity.entity_id},
                )
                self.async_create_issue(
                    issue_id=entity.entity_id,
                    references=unknown_entities,
                    is_fixable=True,
                    data={
                        "group_entity_id": entity.entity_id,
                        # What the fix checks again before dropping any.
                        "group_unknown_entity_ids": ",".join(sorted(unknown_entities)),
                        "group": entity.name,
                        "entities": described,
                    },
                    translation_placeholders={
                        "entities": described,
                        "group": entity.name,
                        "entity_id": entity.entity_id,
                    },
                )
                LOGGER.debug(
                    "Spook found unknown member entities in %s "
                    "and created an issue for it; Entities: %s",
                    entity.entity_id,
                    ", ".join(unknown_entities),
                )
