"""Spook - Your homie. The trigger IDs an automation has, and the ones it checks.

A trigger condition, or a template comparing `trigger.id`, that names an ID
none of the automation's own triggers has can never match. Home Assistant
loads it without a word, and the branch behind it silently never runs.

Everything in here reads the raw configuration and answers `None` when it
cannot be sure. A wrong answer here reports a working automation as broken,
and missing one only means a ghost that stays hidden a little longer.
"""

from __future__ import annotations

from typing import Any

from .reference_extraction import (
    VALUE_KEYS,
    names_given_to_templates,
    without_disabled_steps,
    without_never_rendered,
)
from .template_extraction import (
    extract_template_strings_from_config,
    extract_trigger_ids_from_template,
    is_template_string,
)

# Where an automation keeps its triggers, the current name and the old one.
# Home Assistant takes either, never both.
_TRIGGER_KEYS = ("triggers", "trigger")

# Parts of an automation where `trigger` is not the trigger that started it:
# the triggers themselves, and the variables rendered before any of them fired.
_BEFORE_A_TRIGGER = frozenset({*_TRIGGER_KEYS, "trigger_variables"})


def _flattened(triggers: Any) -> list[Any]:
    """Return the triggers the way Home Assistant counts them.

    A trigger can be a single one rather than a list, and an item holding
    nothing but `triggers:` is a group whose triggers are taken in its place.
    One level only, like `cv._base_trigger_list_flatten`.
    """
    if not isinstance(triggers, list):
        triggers = [triggers]

    flattened: list[Any] = []
    for trigger in triggers:
        if isinstance(trigger, dict) and "triggers" in trigger and len(trigger) == 1:
            grouped = trigger["triggers"]
            flattened.extend(grouped if isinstance(grouped, list) else [grouped])
        else:
            flattened.append(trigger)
    return flattened


def trigger_ids_of(config: Any) -> frozenset[str] | None:
    """Return every ID the triggers of an automation hand over.

    A trigger's own `id`, or without one its position in the list as text,
    counted from `0` over the flattened list. Disabled triggers count too:
    Home Assistant hands out the positions before it skips them, and an ID
    that belongs to a trigger somebody parked is not an unknown one.

    `None` when that cannot be known: no triggers to read, or an ID that is
    not text. Home Assistant refuses the latter, so the automation never
    loads anyway. An `id` under `options` is also `None`: Home Assistant
    lifts the options of some triggers to the top, where it would replace
    the trigger's own.
    """
    if not isinstance(config, dict):
        return None

    key = next((key for key in _TRIGGER_KEYS if key in config), None)
    if key is None:
        return None

    ids: set[str] = set()
    for position, trigger in enumerate(_flattened(config[key])):
        if not isinstance(trigger, dict):
            return None

        options = trigger.get("options")
        if isinstance(options, dict) and "id" in options:
            return None

        if "id" not in trigger:
            ids.add(str(position))
            continue

        if not isinstance(trigger_id := trigger["id"], str):
            return None
        ids.add(trigger_id)

    return frozenset(ids)


def _condition_ids(value: Any) -> set[str]:
    """Return the IDs a trigger condition checks for, as Home Assistant reads them.

    One or a list, each turned into text the way `cv.string` does: `id: 1`
    is `"1"`, which matches the second trigger when it has no ID of its own.
    Anything that looks like a template is left out. Home Assistant does not
    render it, but such an ID is far more likely to be filled in from
    somewhere Spook cannot see than to be meant as written.
    """
    values = value if isinstance(value, list) else [value]
    return {
        item if isinstance(item, str) else str(item)
        for item in values
        if item is not None
        and not isinstance(item, (dict, list))
        and not is_template_string(item)
    }


def _walk_trigger_conditions(config: Any, found: set[str]) -> None:
    """Collect the IDs every trigger condition checks for, wherever it nests."""
    if isinstance(config, list):
        for item in config:
            _walk_trigger_conditions(item, found)
        return

    if not isinstance(config, dict):
        return

    if config.get("condition") == "trigger":
        found.update(_condition_ids(config.get("id")))

    for key, value in config.items():
        if key in VALUE_KEYS:
            continue
        _walk_trigger_conditions(value, found)


def checked_trigger_ids(config: Any) -> frozenset[str] | None:
    """Return the trigger IDs an automation checks for.

    The `id` of every trigger condition, at the top and in the actions,
    however deeply nested, and the literals templates compare `trigger.id`
    to. Disabled steps and conditions are left out: they never check
    anything.

    `None` when the automation gives `trigger` a meaning of its own, as a
    variable or a response variable. That replaces the trigger for every
    check after it, and which ones those are is not worth guessing.
    """
    if not isinstance(config, dict) or "trigger" in names_given_to_templates(config):
        return None

    after_a_trigger = without_disabled_steps(
        {key: value for key, value in config.items() if key not in _BEFORE_A_TRIGGER}
    )

    # The automation itself is no condition, whatever its keys are: its own
    # `id` is the automation's, not a trigger's.
    found: set[str] = set()
    for key, value in after_a_trigger.items():
        if key not in VALUE_KEYS:
            _walk_trigger_conditions(value, found)

    for template in extract_template_strings_from_config(
        without_never_rendered(after_a_trigger)
    ):
        found.update(extract_trigger_ids_from_template(template))

    return frozenset(found)


def unknown_trigger_ids(config: Any) -> set[str]:
    """Return the trigger IDs an automation checks for that none of its triggers has."""
    if (known := trigger_ids_of(config)) is None or (
        checked := checked_trigger_ids(config)
    ) is None:
        return set()
    return set(checked - known)
