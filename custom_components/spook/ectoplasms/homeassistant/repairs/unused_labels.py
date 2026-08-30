"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.automation import automations_with_label
from homeassistant.components.script import scripts_with_label
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.util import dt as dt_util

from ....const import LOGGER
from ....reference_extraction import async_collect_mentioned_strings
from ....repairs import AbstractSpookRepair

# Give a freshly created label time to be applied before nagging about it.
_MINIMUM_AGE = timedelta(days=1)


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds labels that are not applied to anything.

    A label that is on no entity, device, or area, and is not targeted by
    any automation or script, is not doing anything. Surfaced as tidiness,
    with a fix flow to remove it.
    """

    domain = "homeassistant"
    repair = "unused_labels"
    inspect_events = {
        EVENT_HOMEASSISTANT_STARTED,
        lr.EVENT_LABEL_REGISTRY_UPDATED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
        dr.EVENT_DEVICE_REGISTRY_UPDATED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_on_reload = True
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        mentioned = async_collect_mentioned_strings(self.hass)

        label_registry = lr.async_get(self.hass)
        area_registry = ar.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)

        cutoff = dt_util.utcnow() - _MINIMUM_AGE
        for label in label_registry.async_list_labels():
            self.possible_issue_ids.add(label.label_id)

            if label.created_at > cutoff:
                # Just created; leave time to apply it to something.
                continue
            if er.async_entries_for_label(entity_registry, label.label_id):
                continue
            if dr.async_entries_for_label(device_registry, label.label_id):
                continue
            if ar.async_entries_for_label(area_registry, label.label_id):
                continue
            if automations_with_label(self.hass, label.label_id):
                continue
            if scripts_with_label(self.hass, label.label_id):
                continue
            if label.label_id in mentioned:
                # Named somewhere in an automation or script without
                # being a target of it, so removing it would break
                # something. Not ours to offer up.
                continue

            self.async_create_issue(
                issue_id=label.label_id,
                is_fixable=True,
                data={"unused_label_id": label.label_id, "label": label.name},
                translation_placeholders={"label": label.name},
            )
