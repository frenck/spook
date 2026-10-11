"""Spook - Your homie. The users a configuration names by their ID.

Home Assistant gives every user a random ID when it is made, and never hands
the same one out again. So an ID no user has is not a user that has yet to
show up: it is one that was removed. Only something shaped like such an ID is
judged. Anything else may well be a mistake too, but it was never a user, and
saying it was one that got removed would be wrong.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# How Home Assistant makes a user ID: `uuid.uuid4().hex`.
_USER_ID_SHAPE = re.compile(r"[0-9a-f]{32}")


def is_user_id_shaped(value: Any) -> bool:
    """Return whether this could be an ID Home Assistant gave a user."""
    return isinstance(value, str) and bool(_USER_ID_SHAPE.fullmatch(value))


async def async_get_user_ids(hass: HomeAssistant) -> set[str]:
    """Return the ID of every user, the ones Home Assistant made itself too."""
    return {user.id for user in await hass.auth.async_get_users()}


# A custom card is whatever its author made it. Its keys can look like the
# frontend's and mean something else entirely, so nothing in it is read but
# its visibility, which the frontend applies to every card the same way.
_CUSTOM_PREFIX = "custom:"

_LOGICAL_CONDITIONS = frozenset({"and", "or", "not"})
_USER_CONDITION = "user"

# What a performed action hands to Home Assistant is the action's business,
# not the dashboard's.
_PERFORMED_ACTION_PAYLOAD_KEYS = frozenset({"data", "service_data", "target"})


def _user_ids(values: Any) -> set[str]:
    """Return the user IDs in a list, leaving out anything else."""
    if not isinstance(values, list):
        return set()
    return {value for value in values if is_user_id_shaped(value)}


def _listed_users(items: Any) -> set[str]:
    """Return the users of a list of `{user: ...}`, like a view's `visible`."""
    if not isinstance(items, list):
        return set()
    return _user_ids([item.get("user") for item in items if isinstance(item, dict)])


def _add_conditions(conditions: Any, found: set[str]) -> None:
    """Add the users named by user conditions, however deep they nest."""
    items = conditions if isinstance(conditions, list) else [conditions]
    for condition in items:
        if not isinstance(condition, dict):
            continue

        # Switched off is not looked at by the frontend. One that a template
        # switches on or off is only known to core.
        if condition.get("enabled", True) is not True:
            continue

        kind = condition.get("condition")
        if kind in _LOGICAL_CONDITIONS:
            _add_conditions(condition.get("conditions"), found)
        elif kind == _USER_CONDITION:
            found.update(_user_ids(condition.get("users")))


def _collect(node: dict[str, Any], found: set[str]) -> None:
    """Collect the users one dashboard node names, leaving what it holds."""
    # Only the conditional card, row and element read `conditions` like this.
    if node.get("type") == "conditional":
        _add_conditions(node.get("conditions", []), found)

    # Tapping something that asks first, except for these users.
    if isinstance(confirmation := node.get("confirmation"), dict):
        found.update(_listed_users(confirmation.get("exemptions")))


def _walk(node: Any, found: set[str], *, is_view: bool = False) -> None:
    """Collect the users named in a dashboard node, and everything under it."""
    if isinstance(node, list):
        for item in node:
            _walk(item, found, is_view=is_view)
        return

    if not isinstance(node, dict):
        return

    # The way to show a view to some users only. The frontend applies it to
    # every view, a custom one too. A view has no `visibility`: only its
    # cards, badges, sections and sidebar do.
    if is_view:
        found.update(_listed_users(node.get("visible")))
    else:
        # Every card, badge and section can be made visible to some users.
        _add_conditions(node.get("visibility", []), found)

    node_type = node.get("type")
    if isinstance(node_type, str) and node_type.startswith(_CUSTOM_PREFIX):
        return

    _collect(node, found)

    for key, value in node.items():
        # A strategy stores options for cards it makes, not cards.
        if key == "strategy" or key in _PERFORMED_ACTION_PAYLOAD_KEYS:
            continue
        if isinstance(value, (dict, list)):
            _walk(value, found, is_view=key == "views")


def extract_user_ids_from_dashboard_node(node: Any) -> set[str]:
    """Return the user IDs named anywhere in a dashboard node.

    Takes any part of a dashboard: a whole one, a card, or a view when it is
    one of the views of a dashboard. Only where the frontend compares them
    with the user looking: user conditions, the users a view is visible to,
    and the users a confirmation does not ask.
    """
    found: set[str] = set()
    _walk(node, found)
    return found


def extract_user_ids_from_view(view: Any) -> set[str]:
    """Return the user IDs named anywhere in a view, its own `visible` too."""
    found: set[str] = set()
    _walk(view, found, is_view=True)
    return found
