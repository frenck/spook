"""Spook - Your homie. Telling an empty area, floor or label from a used one."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .reference_extraction import async_referencing

if TYPE_CHECKING:
    from collections.abc import Container

    from homeassistant.core import HomeAssistant

    from .reference_extraction import CoreReferenceKind

# In one place because two things ask it and they must not drift: the repair
# that offers to remove one, and the fix that does. The fix asks again right
# before it deletes anything, because an issue can sit there for days and
# something may have moved in since.
#
# `mentioned` is every string named somewhere in an automation or script
# without being a target of it. That is not proof of use: it takes every
# string it finds, and a coincidence counts the same as a reference. It is
# enough to stop offering to delete something, which is all this decides.


def _targeted_by_automation_or_script(
    hass: HomeAssistant, kind: CoreReferenceKind, reference: str
) -> bool:
    """Return whether Home Assistant says an automation or script targets this.

    Asked one automation or script at a time, rather than through
    `automations_with_area` and its siblings. Those give up on the first
    automation Home Assistant cannot read. What that one names as a plain
    string is still in `mentioned`, so it keeps this in use either way.
    """
    return any(
        async_referencing(hass, domain, kind, reference)
        for domain in (AUTOMATION_DOMAIN, SCRIPT_DOMAIN)
    )


def _vacuum_cleans_area(hass: HomeAssistant, area_id: str) -> bool:
    """Return whether a vacuum has rooms of its own mapped to this area.

    That mapping is made by hand, and it is how cleaning an area by name
    works, from an action or by voice. An area that only a vacuum knows is
    still a room someone asks to have cleaned.
    """
    return any(
        area_id in (entry.options.get(VACUUM_DOMAIN, {}).get("area_mapping") or {})
        for entry in er.async_get(hass).entities.values()
    )


def async_area_in_use(
    hass: HomeAssistant,
    area_id: str,
    mentioned: Container[str],
) -> bool:
    """Return whether anything lives in, targets, names or cleans this area."""
    return bool(
        dr.async_entries_for_area(dr.async_get(hass), area_id)
        or er.async_entries_for_area(er.async_get(hass), area_id)
        or _targeted_by_automation_or_script(hass, "areas", area_id)
        or area_id in mentioned
        or _vacuum_cleans_area(hass, area_id)
    )


def async_floor_in_use(
    hass: HomeAssistant,
    floor_id: str,
    mentioned: Container[str],
) -> bool:
    """Return whether any area is on, or anything targets or names, this floor."""
    return bool(
        ar.async_entries_for_floor(ar.async_get(hass), floor_id)
        or _targeted_by_automation_or_script(hass, "floors", floor_id)
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
        or _targeted_by_automation_or_script(hass, "labels", label_id)
        or label_id in mentioned
    )
