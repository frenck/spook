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

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENABLED,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    MATCH_ALL,
)
from homeassistant.core import callback, valid_entity_id
from homeassistant.helpers.entity_component import DATA_INSTANCES

from .template_extraction import (
    KNOWN_DOMAINS,
    extract_attribute_pairs_from_template,
    extract_state_pairs_from_template,
    extract_template_strings_from_config,
    is_template_string,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

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


# Where an event trigger keeps what it matches on, rather than what it needs.
_EVENT_PAYLOAD_KEYS = frozenset({"event_data", "event_data_template"})


def event_payload_keys_to_leave_alone(config: dict[str, Any]) -> frozenset[str]:
    """Return the event payload keys that hold data rather than references.

    An `entity_id` inside `event_data` is a reference when the event comes
    from an integration that means it that way, `timer.finished` being the
    usual one. On somebody's own event it is whatever the sender put there,
    and reporting that as a missing entity is a repair about an automation
    that works perfectly well.

    Told apart by the event type: one named after a domain comes from that
    integration, anything else is somebody's own. Only on an event trigger:
    action data can carry an `event_type` and `event_data` of its own, and
    there they are whatever that action takes.
    """
    if config.get("trigger", config.get("platform")) != "event":
        return frozenset()

    event_types = config.get("event_type")
    if event_types is None:
        return frozenset()

    if isinstance(event_types, str):
        event_types = [event_types]

    for event_type in event_types:
        if not isinstance(event_type, str):
            continue

        domain, dot, _ = event_type.partition(".")
        if dot and domain in KNOWN_DOMAINS:
            return frozenset()

    return _EVENT_PAYLOAD_KEYS


def custom_event_payload_entities(config: Any) -> set[str]:
    """Return the entities Home Assistant takes from somebody's own events.

    Core's own reading takes the `entity_id` of the `event_data` of every
    event trigger, top level or waited for in a step, whoever sends the
    event. On somebody's own event that is whatever the sender put there, so
    the repairs take these back out of what core says is referenced.

    Only those named nowhere else in the configuration. One that also shows
    up as a value somewhere else, like a `scene: scene.movie` step, may be a
    reference only core reads, and stays.
    """
    payload: set[str] = set()
    elsewhere: set[str] = set()
    _collect_event_payload_entities(config, payload, elsewhere, in_payload=False)
    return payload - elsewhere


def _collect_event_payload_entities(
    config: Any, payload: set[str], elsewhere: set[str], *, in_payload: bool
) -> None:
    """Collect the entities of custom event payloads, and every other value."""
    if isinstance(config, str):
        elsewhere.add(config)
        return
    if isinstance(config, list):
        for item in config:
            _collect_event_payload_entities(
                item, payload, elsewhere, in_payload=in_payload
            )
        return
    if not isinstance(config, dict):
        return

    # Action data is whatever the action takes, never a trigger, whatever
    # its shape.
    payload_keys = (
        frozenset() if in_payload else event_payload_keys_to_leave_alone(config)
    )
    if payload_keys and isinstance(event_data := config.get("event_data"), dict):
        entity_id = event_data.get(ATTR_ENTITY_ID)
        if isinstance(entity_id, str) and valid_entity_id(entity_id):
            payload.add(entity_id)

    for key, value in config.items():
        if key not in payload_keys:
            _collect_event_payload_entities(
                value,
                payload,
                elsewhere,
                in_payload=in_payload or key in _PAYLOAD_KEYS,
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


# Keys whose value is payload, not steps: service data, variables and event
# data hold whatever somebody put there, and an `enabled: false` in them is
# theirs, not a parked step.
_PAYLOAD_KEYS = _EXCLUDED_KEYS | frozenset({"data", "data_template", "service_data"})


def without_disabled_steps(config: Any, *, in_payload: bool = False) -> Any:
    """Return a copy of ``config`` without its disabled steps.

    A step, trigger or condition carrying ``enabled: false`` is left out of
    the copy, whether it sits in a list or is written on its own. Nothing
    under a payload key is touched: service data, variables and event data
    are arbitrary, and a dict in there with an ``enabled`` key of its own is
    not a step.
    """
    if isinstance(config, list):
        return [
            without_disabled_steps(item, in_payload=in_payload)
            for item in config
            if in_payload
            or not (isinstance(item, dict) and item.get(CONF_ENABLED) is False)
        ]
    if isinstance(config, dict):
        # A single step can also be written without a list, as the value of
        # a key like `actions` or `then`. Parked like that, the key goes.
        return {
            key: without_disabled_steps(
                value, in_payload=in_payload or key in _PAYLOAD_KEYS
            )
            for key, value in config.items()
            if in_payload
            or key in _PAYLOAD_KEYS
            or not (isinstance(value, dict) and value.get(CONF_ENABLED) is False)
        }
    return config


def only_in_disabled_steps(config: Any, extract: Callable[[Any], set[str]]) -> set[str]:
    """Return what ``extract`` finds in ``config`` only in disabled steps.

    A disabled step does nothing, and people disable one on purpose to park
    it. What only such a step names cannot break a run, so it is not worth a
    repair; what a step that runs names as well still is.
    """
    return extract(config) - extract(without_disabled_steps(config))


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


# Triggers and conditions with an `attribute:` that names an attribute of the
# entities they watch. Numeric state is in here too: same field, same meaning.
_ATTRIBUTE_PLATFORMS = frozenset({"numeric_state", "state"})

# Spook's own state trigger keeps its attribute under `options`.
_SPOOK_STATE_CHANGED = "spook.state_changed"


def _literal_entity_ids(value: Any) -> list[str]:
    """Return the entity IDs, or registry IDs, written out in a config value."""
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list):
        values = [item for item in value if isinstance(item, str)]
    else:
        return []

    return [
        item.strip()
        for item in values
        if item.strip()
        and item.strip() not in (ENTITY_MATCH_ALL, ENTITY_MATCH_NONE)
        and not is_template_string(item)
    ]


@dataclass(frozen=True, slots=True)
class NamedReferences:
    """The attributes, or states, a configuration names, and of which entities."""

    # Written out: the entity, or a registry ID, and the attribute or state.
    pairs: frozenset[tuple[str, str]]
    # Spook's own state triggers, and the attribute or state each names.
    # Which entities that is depends on the house as it is right now, so it
    # is left to the caller to resolve, the way the trigger does.
    followed: tuple[tuple[dict[str, Any], str], ...]


def _attribute_reference(config: dict[str, Any]) -> tuple[Any, Any] | None:
    """Return the entity IDs and attribute a trigger or condition watches."""
    # `trigger` is also the list of triggers itself, in old style configs.
    condition = config.get("condition")
    trigger = config.get("trigger") or config.get("platform")
    if not isinstance(condition, str):
        condition = None
    if not isinstance(trigger, str) or "condition" in config:
        trigger = None

    if _ATTRIBUTE_PLATFORMS.intersection((condition, trigger)):
        return config.get("entity_id"), config.get("attribute")

    return None


def _followed_attribute(config: dict[str, Any]) -> str | None:
    """Return the attribute a Spook state trigger follows, if it is one."""
    trigger = config.get("trigger") or config.get("platform")
    if trigger != _SPOOK_STATE_CHANGED or "condition" in config:
        return None

    options = config.get("options")
    attribute = options.get("attribute") if isinstance(options, dict) else None
    return attribute if _is_literal_attribute(attribute) else None


def _is_literal_attribute(attribute: Any) -> bool:
    """Return whether an attribute is written out, rather than worked out."""
    return (
        isinstance(attribute, str)
        and bool(attribute)
        and not is_template_string(attribute)
    )


def _walk_attribute_references(
    config: Any,
    found: set[tuple[str, str]],
    followed: list[tuple[dict[str, Any], str]],
) -> None:
    """Recursively collect the attributes triggers and conditions watch."""
    if isinstance(config, list):
        for item in config:
            _walk_attribute_references(item, found, followed)
        return

    if not isinstance(config, dict):
        return

    if (reference := _attribute_reference(config)) is not None:
        entity_ids, attribute = reference
        if _is_literal_attribute(attribute):
            found.update(
                (entity_id, attribute) for entity_id in _literal_entity_ids(entity_ids)
            )
    elif (attribute := _followed_attribute(config)) is not None:
        followed.append((config, attribute))

    for key, value in config.items():
        if key in _PLATFORM_KEY_EXCLUDED_KEYS:
            continue
        _walk_attribute_references(value, found, followed)


# Keys whose text Home Assistant shows but never renders. A description with
# an example template in it is documentation, not a lookup.
_NEVER_RENDERED_KEYS = frozenset({"alias", "description", "fields"})


def _without_never_rendered(config: Any) -> Any:
    """Return the configuration without the parts that are never rendered.

    Payloads are kept whole, whatever their keys are called: the data of an
    action can have a `description` too, like a calendar event.
    """
    if isinstance(config, dict):
        return {
            key: value if key in _PAYLOAD_KEYS else _without_never_rendered(value)
            for key, value in config.items()
            if key not in _NEVER_RENDERED_KEYS
        }
    if isinstance(config, list):
        return [_without_never_rendered(item) for item in config]
    return config


# Where a configuration names what its templates get to see. Each of them
# is handed to every template as a variable, and a variable goes before
# what Home Assistant offers under that name: `variables` of the whole
# thing, of a trigger, or of a step, the variables only the triggers see,
# and what a step stores its response in.
_VARIABLE_BLOCKS = frozenset({"trigger_variables", "variables"})
_RESPONSE_VARIABLE = "response_variable"


def _names_given_by(key: str, value: Any) -> set[str]:
    """Return the names one key of a configuration gives its templates."""
    if key in _VARIABLE_BLOCKS and isinstance(value, dict):
        return {name for name in value if isinstance(name, str)}
    if key == _RESPONSE_VARIABLE and isinstance(value, str):
        return {value}
    return set()


def _collect_names(node: Any, names: set[str]) -> None:
    """Collect the names a part of a configuration gives its templates."""
    if isinstance(node, list):
        for item in node:
            _collect_names(item, names)
        return
    if not isinstance(node, dict):
        return

    for key, value in node.items():
        names |= _names_given_by(key, value)
        # A variable block's values are not names, and what is handed to an
        # action belongs to whatever is called: `variables` in the data of
        # `script.turn_on` are the called script's, not this one's.
        if key not in _PAYLOAD_KEYS and key != _RESPONSE_VARIABLE:
            _collect_names(value, names)


def names_given_to_templates(config: Any) -> frozenset[str]:
    """Return every name a configuration gives its templates.

    Its variables wherever they are set, what steps store a response in,
    and for a script the fields it is called with. Taken from all of it,
    disabled steps too and wherever it nests: a name taken for a variable
    that is not one only means a lookup that is not checked.
    """
    names: set[str] = set()
    if isinstance(config, dict) and isinstance(fields := config.get("fields"), dict):
        names.update(name for name in fields if isinstance(name, str))

    _collect_names(config, names)
    return frozenset(names)


def extract_attribute_references_from_config(config: Any) -> NamedReferences:
    """Return the attributes a raw configuration names, and of which entities.

    The `attribute:` of every state and numeric state trigger and condition,
    wherever it nests (`and`, `or`, `not`, `choose`, `if`, `repeat`,
    `wait_for_trigger`, condition steps), and the literal pairs in every
    template that is rendered. Each entity of a list makes a pair of its own. Spook's own
    state trigger is handed back as it is, with the attribute it follows.

    Disabled steps, triggers and conditions are left out: they do nothing,
    so nothing they name can break anything.

    An entity can be a registry ID, which is what the editor writes in some
    places; resolving those is up to the caller, which has the registry.

    A template is not read for a lookup whose name the configuration gives
    a meaning of its own, like a variable called `states`.
    """
    pruned = without_disabled_steps(config)
    shadowed = names_given_to_templates(config)

    found: set[tuple[str, str]] = set()
    followed: list[tuple[dict[str, Any], str]] = []
    _walk_attribute_references(pruned, found, followed)

    for template in extract_template_strings_from_config(
        _without_never_rendered(pruned)
    ):
        found.update(extract_attribute_pairs_from_template(template, shadowed))

    return NamedReferences(pairs=frozenset(found), followed=tuple(followed))


# Where a state trigger, and Spook's own, names the states it waits for.
_STATE_TRIGGER_KEYS = ("from", "not_from", "to", "not_to")


def _literal_states(value: Any, *, in_condition: bool = False) -> list[str]:
    """Return the states written out in a config value, one or a list.

    Only text: Home Assistant refuses anything else, like a `to: on` that
    YAML read as true, so such a trigger never loads to wait for anything.
    `*` is any state. A state condition compares a state shaped like an
    input helper's entity ID with that helper's state instead, which is not
    something written out. Core spells that as `input_` and a few domains;
    any of them is left alone here, so a new one cannot slip through.
    """
    values = value if isinstance(value, list) else [value]
    return [
        item
        for item in values
        if isinstance(item, str)
        and item
        and item != MATCH_ALL
        and not is_template_string(item)
        and not (in_condition and valid_entity_id(item) and item.startswith("input_"))
    ]


def _state_reference(config: dict[str, Any]) -> tuple[Any, list[str]] | None:
    """Return the entity IDs and states a state trigger or condition names.

    Only when it is about the state itself: with an `attribute:`, the values
    are that attribute's, which is another check.
    """
    if "attribute" in config:
        return None

    if config.get("condition") == "state":
        return config.get("entity_id"), _literal_states(
            config.get("state"), in_condition=True
        )

    trigger = config.get("trigger") or config.get("platform")
    if trigger == "state" and "condition" not in config:
        return config.get("entity_id"), [
            state
            for key in _STATE_TRIGGER_KEYS
            for state in _literal_states(config.get(key))
        ]

    return None


def _followed_states(config: dict[str, Any]) -> list[str]:
    """Return the states a Spook state trigger names, if it is one.

    Following an attribute, its `to` and `from` are that attribute's values.
    """
    trigger = config.get("trigger") or config.get("platform")
    if trigger != _SPOOK_STATE_CHANGED or "condition" in config:
        return []

    options = config.get("options")
    if not isinstance(options, dict) or "attribute" in options:
        return []
    return [
        state
        for key in _STATE_TRIGGER_KEYS
        for state in _literal_states(options.get(key))
    ]


def _walk_state_references(
    config: Any,
    found: set[tuple[str, str]],
    followed: list[tuple[dict[str, Any], str]],
) -> None:
    """Recursively collect the states triggers and conditions wait for."""
    if isinstance(config, list):
        for item in config:
            _walk_state_references(item, found, followed)
        return

    if not isinstance(config, dict):
        return

    if (reference := _state_reference(config)) is not None:
        entity_ids, states = reference
        found.update(
            (entity_id, state)
            for entity_id in _literal_entity_ids(entity_ids)
            for state in states
        )
    else:
        followed.extend((config, state) for state in _followed_states(config))

    for key, value in config.items():
        if key in _PLATFORM_KEY_EXCLUDED_KEYS:
            continue
        _walk_state_references(value, found, followed)


def extract_state_references_from_config(config: Any) -> NamedReferences:
    """Return the states a raw configuration names, and of which entities.

    The `to`, `from`, `not_to` and `not_from` of every state trigger and the
    `state` of every state condition, wherever they nest, as long as they
    are about the state rather than an attribute. Spook's own state trigger
    is handed back as it is, with each state it names. In templates, only a
    literal `is_state`.

    Disabled steps, triggers and conditions are left out, and an entity can
    be a registry ID, and a name the configuration gives a meaning of its
    own is no lookup, all like the attribute references.
    """
    pruned = without_disabled_steps(config)
    shadowed = names_given_to_templates(config)

    found: set[tuple[str, str]] = set()
    followed: list[tuple[dict[str, Any], str]] = []
    _walk_state_references(pruned, found, followed)

    for template in extract_template_strings_from_config(
        _without_never_rendered(pruned)
    ):
        found.update(extract_state_pairs_from_template(template, shadowed))

    return NamedReferences(pairs=frozenset(found), followed=tuple(followed))


# Only automations and scripts carry a raw configuration worth reading here.
_CONFIGURED_DOMAINS = ("automation", "script")


# Quoted literals inside a template, as in `{{ ['study', 'loft'] }}`.
_QUOTED = re.compile(r"""['"]([^'"]+)['"]""")


def _collect_every_string(node: Any, found: set[str]) -> None:
    """Collect every string anywhere in a configuration, keys included.

    Deliberately indiscriminate. This is not working out what a configuration
    means; it is answering whether something is mentioned in it at all.

    A template counts as one string and also as the literals inside it, since
    `for_each: "{{ ['study'] }}"` names `study` as plainly as a list would.
    Matching on substrings instead would be far too eager: an area called
    `kitchen` would be found in `sensor.kitchen_temperature` and nothing would
    ever be reported again.
    """
    if isinstance(node, str):
        found.add(node)
        if is_template_string(node):
            found.update(_QUOTED.findall(node))
    elif isinstance(node, Mapping):
        for key, value in node.items():
            if isinstance(key, str):
                found.add(key)
            _collect_every_string(value, found)
    elif isinstance(node, (list, tuple, set)):
        for item in node:
            _collect_every_string(item, found)


@callback
def async_collect_mentioned_strings(hass: HomeAssistant) -> set[str]:
    """Return every string appearing in any automation or script.

    For deciding whether something is referenced, `referenced_areas` and
    Spook's own target extraction are the right tools: they know what a
    reference is.

    This is for the other question, the one asked before offering to delete
    something: might this be in use? An area listed in a `repeat` `for_each`
    is a target of nothing and neither extraction reports it, yet the script
    plainly needs it.

    The answer is deliberately loose. A string that happens to match counts
    the same as a real reference, so this proves nothing about what is in use.
    It only decides whether Spook keeps quiet, and on something that offers to
    delete, a coincidence is a fine reason to.
    """
    found: set[str] = set()

    for domain in _CONFIGURED_DOMAINS:
        if not (component := hass.data.get(DATA_INSTANCES, {}).get(domain)):
            continue

        for entity in component.entities:
            if raw_config := getattr(entity, "raw_config", None):
                _collect_every_string(raw_config, found)

    return found
