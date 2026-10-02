"""Spook - Your homie. Telling an empty area, floor or label from a used one."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.automation import (
    automations_with_area,
    automations_with_floor,
    automations_with_label,
)
from homeassistant.components.script import (
    scripts_with_area,
    scripts_with_floor,
    scripts_with_label,
)
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

if TYPE_CHECKING:
    from collections.abc import Container

    from homeassistant.core import HomeAssistant

# In one place because two things ask it and they must not drift: the repair
# that offers to remove one, and the fix that does. The fix asks again right
# before it deletes anything, because an issue can sit there for days and
# something may have moved in since.
#
# `mentioned` is every string named somewhere in an automation or script
# without being a target of it. That is not proof of use: it takes every
# string it finds, and a coincidence counts the same as a reference. It is
# enough to stop offering to delete something, which is all this decides.


def async_area_in_use(
    hass: HomeAssistant,
    area_id: str,
    mentioned: Container[str],
) -> bool:
    """Return whether anything lives in, targets or names this area."""
    return bool(
        dr.async_entries_for_area(dr.async_get(hass), area_id)
        or er.async_entries_for_area(er.async_get(hass), area_id)
        or automations_with_area(hass, area_id)
        or scripts_with_area(hass, area_id)
        or area_id in mentioned
    )


def async_floor_in_use(
    hass: HomeAssistant,
    floor_id: str,
    mentioned: Container[str],
) -> bool:
    """Return whether any area is on, or anything targets or names, this floor."""
    return bool(
        ar.async_entries_for_floor(ar.async_get(hass), floor_id)
        or automations_with_floor(hass, floor_id)
        or scripts_with_floor(hass, floor_id)
        or floor_id in mentioned
    )


def async_label_in_use(
    hass: HomeAssistant,
    label_id: str,
    mentioned: Container[str],
) -> bool:
    """Return whether anything carries, targets or names this label."""
    return bool(
        er.async_entries_for_label(er.async_get(hass), label_id)
        or dr.async_entries_for_label(dr.async_get(hass), label_id)
        or ar.async_entries_for_label(ar.async_get(hass), label_id)
        or automations_with_label(hass, label_id)
        or scripts_with_label(hass, label_id)
        or label_id in mentioned
    )
