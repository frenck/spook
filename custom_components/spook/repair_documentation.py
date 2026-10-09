"""Spook - Your homie. Where the documentation explains each repair."""

from __future__ import annotations

from typing import Final

DOCUMENTATION_URL: Final = "https://spook.boo"

# Each repair, and the page and heading in the documentation that explain it.
# Pages use the file name with hyphens, headings the way the documentation
# turns them into anchors. A test holds every repair to having one here, and
# every anchor to a heading that exists.
REPAIR_DOCUMENTATION: Final = {
    "alert_unknown_entity_references": "alert#unknown-watched-entity",
    "alert_unknown_notifiers": "alert#unknown-notifiers",
    "automation_unknown_area_references": "automation#unknown-referenced-areas",
    "automation_unknown_condition_references": (
        "automation#unknown-referenced-conditions"
    ),
    "automation_unknown_device_references": "automation#unknown-referenced-devices",
    "automation_unknown_entity_references": "automation#unknown-referenced-entities",
    "automation_unknown_floor_references": "automation#unknown-referenced-floors",
    "automation_unknown_label_references": "automation#unknown-referenced-labels",
    "automation_unknown_service_references": "automation#unknown-referenced-actions",
    "automation_unknown_trigger_references": "automation#unknown-referenced-triggers",
    "empty_areas": "homeassistant#empty-areas",
    "empty_floors": "homeassistant#empty-floors",
    "energy_unknown_references": "energy#unknown-referenced-entities",
    "group_unknown_members": "group#unknown-source-entity",
    "homekit_unknown_entity_references": "homekit#unknown-entities",
    "lovelace_duplicate_resources": "lovelace#duplicate-dashboard-resources",
    "lovelace_missing_resources": "lovelace#missing-dashboard-resources",
    "lovelace_unknown_area_references": "lovelace#unknown-referenced-areas",
    "lovelace_unknown_entity_references": "lovelace#unknown-referenced-entities",
    "lovelace_unknown_service_references": "lovelace#unknown-actions",
    "min_max_unknown_sources": "homeassistant#unknown-min-max-helper-members",
    "notify_unknown_group_members": "notify#unknown-group-members",
    "orphaned_statistics": "recorder#orphaned-long-term-statistics",
    "person_unknown_device_trackers": "person#unknown-device-trackers",
    "proximity_unknown_ignored_zones": "proximity#unknown-ignored-zones",
    "proximity_unknown_tracked_entities": (
        "proximity#unknown-tracked-devices-or-persons"
    ),
    "proximity_unknown_zone": "proximity#unknown-zone",
    "scene_unknown_entity_references": "scene#unknown-referenced-entities",
    "script_unknown_area_references": "script#unknown-referenced-areas",
    "script_unknown_condition_references": "script#unknown-referenced-conditions",
    "script_unknown_device_references": "script#unknown-referenced-devices",
    "script_unknown_entity_references": "script#unknown-referenced-entities",
    "script_unknown_floor_references": "script#unknown-referenced-floors",
    "script_unknown_label_references": "script#unknown-referenced-labels",
    "script_unknown_service_references": "script#unknown-referenced-actions",
    "script_unknown_trigger_references": "script#unknown-referenced-triggers",
    "template_unknown_entity_references": "template#unknown-referenced-entities",
    "template_unknown_service_references": "template#unknown-referenced-actions",
    "unknown_area_sensors": "homeassistant#unknown-area-sensors",
    "unknown_customized_entities": "homeassistant#unknown-customized-entities",
    "unknown_engines": "assist-pipeline#unknown-engines",
    "unknown_helper_source_references": "homeassistant#unknown-helper-sources",
    "unused_blueprints": "homeassistant#unused-blueprints",
    "unused_labels": "homeassistant#unused-labels",
}


def repair_documentation_url(repair: str) -> str | None:
    """Return the documentation that explains a repair, if it has any."""
    if (page := REPAIR_DOCUMENTATION.get(repair)) is None:
        return None

    return f"{DOCUMENTATION_URL}/{page}"
