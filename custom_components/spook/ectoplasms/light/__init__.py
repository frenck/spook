"""Spook - Your homie. Adjusting lights that are already on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.light import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_GROUP_ENTITIES,
    STATE_ON,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

# Where a light keeps its members, depending on what kind of group it is. A
# helper group lists entity IDs under `entity_id`; a group belonging to one
# integration, like the ones MQTT builds, gets `group_entities` from Home
# Assistant itself. Reading only the first sort means adjusting the second
# sort's group entity, which is the thing these actions exist to avoid.
_MEMBER_KEYS = (ATTR_ENTITY_ID, ATTR_GROUP_ENTITIES)


def async_lights_that_are_on(hass: HomeAssistant, entity_id: str) -> list[State]:
    """Return the lights behind an entity that are on right now.

    A light group is a light like any other, so one target can stand for one
    light or for twenty. Adjusting the group entity itself is what makes Home
    Assistant average its members and then set every one of them to that
    average: the dim one jumps up, the bright one drops. Working per member is
    the whole point of these actions.

    Lights that are off are left out, which is the other half. Home Assistant
    treats an off light as brightness zero and turns it on from there, so
    dimming a room would light up everything somebody had deliberately
    switched off.

    What comes back is every light that is on, whatever it can do. Each action
    keeps only the ones it has something to say to, since a light with no
    dimmer has no brightness to step and one with no colour has no colour to
    set.
    """
    found: list[State] = []
    seen: set[str] = set()
    todo = [entity_id]

    while todo:
        current = todo.pop()

        # Groups can hold groups, and nothing stops one holding itself. The
        # set is what makes that terminate, so there is no depth limit to
        # trip over.
        if current in seen:
            continue

        seen.add(current)

        if (state := hass.states.get(current)) is None:
            continue

        if (members := _async_members(state)) is not None:
            todo.extend(members)
            continue

        if state.state == STATE_ON:
            found.append(state)

    return found


def _async_members(state: State) -> list[str] | None:
    """Return the lights a group holds, or `None` if it is not a group.

    Told apart by whether the attribute is there rather than by whether it
    holds anything, because a group that is empty is still a group and has no
    brightness of its own worth setting.
    """
    for key in _MEMBER_KEYS:
        if key not in state.attributes:
            continue

        members = state.attributes[key]
        if not isinstance(members, (list, tuple)):
            continue

        return [
            member
            for member in members
            if isinstance(member, str) and member.startswith(f"{DOMAIN}.")
        ]

    return None
