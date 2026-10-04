"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.todo import (
    DOMAIN,
    TodoItem,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

ATTR_ITEM = "item"
ATTR_AFTER = "after"
ATTR_POSITION = "position"

POSITION_TOP = "top"
POSITION_BOTTOM = "bottom"


def _find(value: str, items: list[TodoItem]) -> TodoItem | None:
    """Find an item by its uid or its title, the way `todo.update_item` does."""
    for item in items:
        if value in (item.uid, item.summary):
            return item
    return None


class SpookService(AbstractSpookEntityComponentService[TodoListEntity]):
    """To-do list service that moves an item to another place in the list.

    A to-do list that can reorder its items does so when you drag one in the
    interface, and nowhere else: there is no action for it. An automation
    putting the most urgent chore at the top had no way to.
    """

    domain = DOMAIN
    service = "move_item"
    required_features = [TodoListEntityFeature.MOVE_TODO_ITEM]
    schema = {
        vol.Required(ATTR_ITEM): vol.All(cv.string, vol.Length(min=1)),
        vol.Exclusive(ATTR_AFTER, "where"): vol.All(cv.string, vol.Length(min=1)),
        vol.Exclusive(ATTR_POSITION, "where"): vol.In([POSITION_TOP, POSITION_BOTTOM]),
    }

    async def async_handle_service(
        self,
        entity: TodoListEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        items = list(entity.todo_items or ())

        if (item := _find(call.data[ATTR_ITEM], items)) is None or item.uid is None:
            msg = f"There is no item {call.data[ATTR_ITEM]} in {entity.entity_id}"
            raise ServiceValidationError(msg)

        # Where it goes is said as the item it lands after, the way the list
        # itself takes it. None is the top.
        if (after := call.data.get(ATTR_AFTER)) is not None:
            previous = _find(after, items)
            if previous is None or previous.uid is None:
                msg = f"There is no item {after} in {entity.entity_id}"
                raise ServiceValidationError(msg)
            if previous.uid == item.uid:
                msg = "An item cannot be moved after itself"
                raise ServiceValidationError(msg)
            previous_uid: str | None = previous.uid
        elif call.data.get(ATTR_POSITION) == POSITION_BOTTOM:
            others = [other for other in items if other.uid != item.uid]
            if not others:
                return
            # Without a uid the last item cannot be named, and naming nothing
            # is the top: the opposite end of where it was asked to go.
            if (previous_uid := others[-1].uid) is None:
                msg = f"The last item in {entity.entity_id} cannot be moved after"
                raise ServiceValidationError(msg)
        elif call.data.get(ATTR_POSITION) == POSITION_TOP:
            previous_uid = None
        else:
            msg = "Say where to: after another item, or the top or bottom"
            raise ServiceValidationError(msg)

        # Straight to the list, the way the interface asks it when an item
        # is dragged.
        await entity.async_move_todo_item(uid=item.uid, previous_uid=previous_uid)
