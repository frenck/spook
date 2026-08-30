"""Spook - Your homie. Target reference extraction from raw configurations.

Home Assistant's built-in ``referenced_areas``/``referenced_devices``/
``referenced_floors``/``referenced_labels`` walkers only know a fixed set
of script step types and miss references nested in others (most notably
``repeat`` sequences). This module walks a raw automation or script
configuration generically instead: every ``target:`` block and every
direct reference key is collected, wherever it nests.

Results are meant to be unioned with Home Assistant's built-in extraction,
never to replace it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from homeassistant.const import ENTITY_MATCH_ALL, ENTITY_MATCH_NONE

from .template_extraction import is_template_string

# Direct reference keys, mapped to their reference type.
# What the device registry hands out: `random_uuid_hex`, so 32 hex characters.
# Should that ever change, this errs towards reporting less rather than
# reporting a good automation as broken.
_DEVICE_REGISTRY_ID = re.compile(r"[0-9a-f]{32}")

_REFERENCE_KEYS = (
    "area_id",
    "device_id",
    "floor_id",
    "label_id",
)

# Keys whose subtree carries arbitrary payload data, not references.
# ``event_data`` matches event payloads (an ``area_id`` in there filters
# incoming events); ``variables`` hold user-defined values that only become
# references where they are used.
_EXCLUDED_KEYS = frozenset(
    {
        "event_data",
        "event_data_template",
        "variables",
        "trigger_variables",
    },
)


@dataclass
class ExtractedTargets:
    """Target references extracted from a raw configuration."""

    area_ids: set[str] = field(default_factory=set)
    device_ids: set[str] = field(default_factory=set)
    floor_ids: set[str] = field(default_factory=set)
    label_ids: set[str] = field(default_factory=set)


def is_pattern_reference(value: str) -> bool:
    """Return whether a reference is a pattern rather than a name.

    Cards and helpers that take a filter read ``KG/*`` as every area under
    ``KG``. Home Assistant has no area, floor or label called ``KG/*`` and
    never will, so looking one up and finding nothing says nothing about
    whether the dashboard works. Reported as #1514.

    Only for areas, floors and labels. An entity ID has a shape, and
    ``light.*`` is already turned away for not having it.
    """
    return "*" in value


def _collect_ids(value: Any) -> set[str]:
    """Return the plain string IDs in a config value.

    Templated values cannot be resolved statically, the ``all``/``none``
    match constants are not references, and a pattern is not a name; all
    three are skipped.
    """
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [item for item in value if isinstance(item, str)]
    else:
        return set()

    return {
        item
        for item in values
        if item
        and item not in (ENTITY_MATCH_ALL, ENTITY_MATCH_NONE)
        and not is_template_string(item)
        and not is_pattern_reference(item)
    }


def _walk(config: Any, targets: ExtractedTargets) -> None:
    """Recursively collect target references from a configuration node."""
    if isinstance(config, list):
        for item in config:
            _walk(item, targets)
        return

    if not isinstance(config, dict):
        return

    for key in _REFERENCE_KEYS:
        if key not in config:
            continue

        ids = _collect_ids(config[key])

        if key == "device_id":
            # Some integrations take a `device_id` of their own making as
            # plain action data, RFLink's protocol IDs among them, and those
            # are not registry IDs and never will be. Reporting one as a
            # missing device would be a repair about a perfectly good
            # automation, which is worse than missing a real one.
            ids = {value for value in ids if _DEVICE_REGISTRY_ID.fullmatch(value)}

        getattr(targets, f"{key}s").update(ids)

    for key, value in config.items():
        if key in _EXCLUDED_KEYS:
            continue
        _walk(value, targets)


def extract_targets_from_config(config: Any) -> ExtractedTargets:
    """Extract area, device, floor, and label references from a raw config.

    Walks the entire configuration structure, covering targets nested in
    any script step type (including ``repeat``), triggers, conditions, and
    ``wait_for_trigger`` blocks alike.
    """
    targets = ExtractedTargets()
    _walk(config, targets)
    return targets


# Additional keys whose subtree carries payload or opaque data when
# extracting trigger and condition platform keys. Service data can hold
# keys like ``platform`` or ``condition`` (a weather condition, for
# example), and blueprint inputs are free-form.
_PLATFORM_KEY_EXCLUDED_KEYS = _EXCLUDED_KEYS | frozenset(
    {
        "data",
        "data_template",
        "service_data",
        "use_blueprint",
    },
)


@dataclass
class ExtractedPlatformKeys:
    """Trigger and condition platform keys extracted from a raw config."""

    trigger_keys: set[str] = field(default_factory=set)
    condition_keys: set[str] = field(default_factory=set)


def _walk_platform_keys(config: Any, found: ExtractedPlatformKeys) -> None:
    """Recursively collect trigger and condition platform keys."""
    if isinstance(config, list):
        for item in config:
            _walk_platform_keys(item, found)
        return

    if not isinstance(config, dict):
        return

    if isinstance(condition := config.get("condition"), str):
        # `condition: "{{ ... }}"` is Home Assistant's own shorthand for a
        # template condition, and `cv.CONDITION_SCHEMA` takes it. The string
        # is the condition itself, not the name of something that provides
        # one, so reading it as a platform key reports the whole template
        # back at somebody as an integration they do not have. #1520.
        if not is_template_string(condition):
            found.condition_keys.add(condition)
    else:
        # Only collect trigger keys outside condition configurations: the
        # trigger condition carries trigger IDs (not platform keys) in its
        # own ``trigger`` field.
        for key in ("trigger", "platform"):
            if isinstance(trigger := config.get(key), str):
                found.trigger_keys.add(trigger)
                break

    for key, value in config.items():
        if key in _PLATFORM_KEY_EXCLUDED_KEYS:
            continue
        _walk_platform_keys(value, found)


def extract_platform_keys_from_config(config: Any) -> ExtractedPlatformKeys:
    """Extract trigger and condition platform keys from a raw config.

    Collects the type of every trigger (``platform:``/``trigger:``) and
    condition (``condition:``) used anywhere in the configuration,
    including ``wait_for_trigger`` blocks and nested sequences.
    """
    found = ExtractedPlatformKeys()
    _walk_platform_keys(config, found)
    return found
