"""Spook - Your homie. Shared lookups for the category actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import category_registry as cr

from ...const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# The scopes the frontend shows categories in. Home Assistant takes any string
# as a scope, so a typo would make a category that no page ever displays.
SCOPES = ("automation", "helpers", "scene", "script")

# Automations, scripts and scenes each have their own page, and so their own
# scope. Everything else that can carry a category lives on the helpers page.
_OWN_SCOPE = frozenset({"automation", "scene", "script"})


@callback
def async_scope_for_entity(entity_id: str) -> str:
    """Return the scope an entity's category lives in."""
    domain = split_entity_id(entity_id)[0]
    return domain if domain in _OWN_SCOPE else "helpers"


@callback
def async_resolve_category(
    hass: HomeAssistant, scope: str, category: str
) -> cr.CategoryEntry:
    """Find a category by its ID or its name, or raise.

    Category IDs are random and the UI never shows them, and there is no
    template function to look one up either. Without taking the name, these
    actions would only work on categories an automation created itself.
    """
    category_registry = cr.async_get(hass)

    if entry := category_registry.async_get_category(scope=scope, category_id=category):
        return entry

    for entry in category_registry.async_list_categories(scope=scope):
        if entry.name.casefold() == category.casefold():
            return entry

    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="category_not_found",
        translation_placeholders={
            "category": category,
            "scope": scope,
        },
    )
