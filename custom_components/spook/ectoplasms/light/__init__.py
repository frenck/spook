"""Spook - Your homie. Adjusting lights that are already on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

# A group standing for itself, or a group of groups, would otherwise go round
# forever. Nobody nests lights this deep on purpose.
_MOST_NESTING = 10


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
    """
    found: list[State] = []
    seen: set[str] = set()
    todo: list[tuple[str, int]] = [(entity_id, 0)]

    while todo:
        current, depth = todo.pop()

        if current in seen or depth > _MOST_NESTING:
            continue

        seen.add(current)

        if (state := hass.states.get(current)) is None:
            continue

        if members := state.attributes.get(ATTR_ENTITY_ID):
            todo.extend(
                (member, depth + 1)
                for member in members
                if isinstance(member, str) and member.startswith(f"{DOMAIN}.")
            )
            continue

        if (
            state.state == STATE_ON
            and state.attributes.get(ATTR_BRIGHTNESS) is not None
        ):
            found.append(state)

    return found
