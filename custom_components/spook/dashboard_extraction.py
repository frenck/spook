"""Spook - Your homie. Entity reference extraction from dashboard configs.

The Lovelace repair used to hand-walk a fixed set of known card shapes,
missing references in custom cards and any structure it did not explicitly
recurse into. This module walks a dashboard configuration generically: it
recurses through every container and collects entity references from
reference-shaped keys wherever they appear, so custom cards are covered
for free.

Only recognized keys are read; arbitrary strings are never collected. The
downstream ``async_filter_known_entity_ids`` still validates every value,
so a benign string under a recognized key is dropped rather than reported.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import ENTITY_MATCH_ALL, ENTITY_MATCH_NONE
from homeassistant.core import valid_entity_id

from .entity_filtering import (
    IGNORED_ENTITY_DOMAINS,
    NEVER_AN_ENTITY_PREFIXES,
    split_comma_separated_entity_ids,
)
from .reference_extraction import is_pattern_reference
from .template_extraction import KNOWN_DOMAINS

if TYPE_CHECKING:
    from collections.abc import Iterator

# Keys whose value holds one or more entity references, anywhere in a
# dashboard configuration. Values may be a single entity ID, a
# comma-separated list, or a list of entity IDs; entity IDs nested inside
# dicts (like entities-card rows) are reached by the recursion instead.
_ENTITY_REFERENCE_KEYS = frozenset(
    {
        "badges",
        "camera_image",
        "entities",
        "entity",
        "entity_id",
        "entity_ids",
        "exclude_entities",
        "favorite_entities",
        "image_entity",
        "include_entities",
    },
)


# Keys whose subtree says which entities to pick rather than naming any.
# `filter` is what auto-entities and the cards that copy it use, and what is
# under one describes a selection: a domain, an area, a state, a pattern. None
# of it names a particular entity, so reading it as a reference produces
# repairs about dashboards that work perfectly well. #1514 was `area: KG/*`,
# meaning every area under KG, reported as an area that had gone missing.
_MATCHER_KEYS = frozenset({"filter"})

# Except for this one. `options` is not a matcher: it is card configuration
# handed to whatever matched, and it can name entities of its own, a nested
# card with fixed rows among them. Those are on the dashboard and worth
# checking, so the walk goes back in there.
#
# It is also where #1468 was found, `entity: this.entity_id` standing for
# whichever entity matched. That one is turned away at the gate rather than
# here, by not being an entity anybody could have.
_NOT_A_MATCHER = "options"


def _options_within(node: Any) -> Iterator[Any]:
    """Yield the `options` blocks inside a matcher subtree."""
    if isinstance(node, list):
        for item in node:
            yield from _options_within(item)
        return

    if not isinstance(node, dict):
        return

    for key, value in node.items():
        if key == _NOT_A_MATCHER:
            if isinstance(value, (dict, list)):
                yield value
        else:
            yield from _options_within(value)


def _worth_descending_into(node: dict[str, Any]) -> Iterator[Any]:
    """Yield the subtrees of a node that can hold references."""
    for key, value in node.items():
        if key in _MATCHER_KEYS:
            yield from _options_within(value)
        elif isinstance(value, (dict, list)):
            yield value


# Placeholders a custom card hands to whatever it renders, standing for the
# row's own entity. `template-entity-row` and the Mushroom templates both use
# `config.entity`. Shaped exactly like an entity ID, so everything downstream
# takes it for one.
#
# Kept here rather than in the shared `NEVER_AN_ENTITY`, which nine repairs
# read. This is meaningless in a dashboard and could be a real dangling
# reference in a scene or a customization, and only this walk knows which it
# is looking at.
_CARD_PLACEHOLDERS = frozenset({"config.entity"})


def _collect_strings(value: Any, entities: set[str]) -> None:
    """Collect entity IDs from a recognized key's string or list value."""
    if isinstance(value, str):
        entities.update(split_comma_separated_entity_ids(value))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                entities.update(split_comma_separated_entity_ids(item))

    entities.difference_update(_CARD_PLACEHOLDERS)


# Bubble Card names entities under keys of its own. A pop-up can open on an
# entity's state (`trigger_entity`), and a horizontal buttons stack numbers its
# buttons, each with an entity and a motion sensor to sort by (`1_entity`,
# `1_pir_sensor`, and so on). Only read on Bubble Card itself: a key shaped
# like `1_entity` on some other card is that card's business.
_BUBBLE_CARD_TYPE = "custom:bubble-card"
_BUBBLE_CARD_ENTITY_KEYS = frozenset({"trigger_entity"})
_BUBBLE_CARD_NUMBERED_ENTITY_KEY = re.compile(r"\d+_(?:entity|pir_sensor)")


def _collect_bubble_card(node: dict[str, Any], entities: set[str]) -> None:
    """Collect the entities Bubble Card names under keys of its own."""
    for key, value in node.items():
        if key in _BUBBLE_CARD_ENTITY_KEYS or (
            isinstance(key, str) and _BUBBLE_CARD_NUMBERED_ENTITY_KEY.fullmatch(key)
        ):
            _collect_strings(value, entities)


# The areas strategies keep per-area options under `areas_options`, keyed by
# area ID: the dashboard strategy, and the overview view it hands them to.
# Each area's `groups_options` hides and orders entities per group, and those
# two lists are entity IDs. The view of a single area, the `area` view
# strategy, carries its `groups_options` directly. `hidden` and `order` mean
# anything elsewhere, so they are only read in exactly these spots.
_AREAS_STRATEGY_TYPES = frozenset({"areas", "areas-overview"})
_AREA_VIEW_STRATEGY_TYPE = "area"
_AREA_GROUP_ENTITY_KEYS = ("hidden", "order")


def _areas_options(node: dict[str, Any]) -> dict[Any, Any]:
    """Return the per-area options of an areas strategy, if this is one."""
    if not isinstance(strategy_type := node.get("type"), str):
        return {}
    if strategy_type not in _AREAS_STRATEGY_TYPES:
        return {}
    if not isinstance(areas_options := node.get("areas_options"), dict):
        return {}
    return areas_options


def _collect_group_entities(groups_options: Any, entities: set[str]) -> None:
    """Collect the entities hidden or ordered in an area's groups."""
    if not isinstance(groups_options, dict):
        return

    for group in groups_options.values():
        if not isinstance(group, dict):
            continue
        for key in _AREA_GROUP_ENTITY_KEYS:
            _collect_strings(group.get(key), entities)


def _collect_areas_strategy_entities(node: dict[str, Any], entities: set[str]) -> None:
    """Collect the entities the areas strategies hide or order per area."""
    # The area card says `type: area` too, but has no `groups_options`.
    if node.get("type") == _AREA_VIEW_STRATEGY_TYPE:
        _collect_group_entities(node.get("groups_options"), entities)

    for area_options in _areas_options(node).values():
        if isinstance(area_options, dict):
            _collect_group_entities(area_options.get("groups_options"), entities)


# A logbook card filters entries by the entity they are filed under, and
# `logbook.log` files them under any ID of the right shape. People make one up
# to group their own entries, like `log.critical_messages`, and the card shows
# them. One under no entity domain at all is left alone; a `light.kitchen` in
# there is meant to be that light, and stays checked.
_LOGBOOK_CARD_TYPE = "logbook"
_LOGBOOK_FILTER_KEYS = ("entities", "target")


def _walk(node: Any, entities: set[str]) -> None:
    """Recursively collect entity references from a configuration node."""
    if isinstance(node, list):
        for item in node:
            _walk(item, entities)
        return

    if not isinstance(node, dict):
        return

    if node.get("type") == _LOGBOOK_CARD_TYPE:
        # Only its filter. The rest of the card, like a visibility condition,
        # is read as on any other card.
        filters = {key: node[key] for key in _LOGBOOK_FILTER_KEYS if key in node}
        found: set[str] = set()
        _walk_node(filters, found)
        entities.update(
            entity_id
            for entity_id in found
            # Any case: one with capitals is still meant as that entity, and
            # the dashboard repair reports how it is written.
            if entity_id.partition(".")[0].lower() in KNOWN_DOMAINS
        )
        node = {
            key: value for key, value in node.items() if key not in _LOGBOOK_FILTER_KEYS
        }

    _walk_node(node, entities)


def _walk_node(node: dict[str, Any], entities: set[str]) -> None:
    """Collect entity references from one dashboard node and what it holds."""
    for key in _ENTITY_REFERENCE_KEYS:
        if key in node:
            _collect_strings(node[key], entities)

    if node.get("type") == _BUBBLE_CARD_TYPE:
        _collect_bubble_card(node, entities)

    _collect_areas_strategy_entities(node, entities)

    for child in _worth_descending_into(node):
        _walk(child, entities)


def extract_entities_from_dashboard_node(node: Any) -> set[str]:
    """Return the entity references found anywhere in a dashboard node.

    Accepts any part of a dashboard configuration (a whole config, a view,
    a card) and returns every entity reference reachable from it.
    """
    entities: set[str] = set()
    _walk(node, entities)
    return entities


# Core cards whose `entity` takes an entity ID and nothing else, as the
# frontend has them in `src/panels/lovelace/cards/types.ts`. The card looks
# whatever is there up in the states as written, so a value that is no entity
# ID at all, like `cover.blind.current_position`, finds nothing and the card
# stays empty. Nothing else on the dashboard gets this far: what a custom card
# does with its fields is its own business.
#
# Not the statistic card: it takes a statistic ID, and an external one like
# `sensor:energy_total` is no entity ID and works fine.
_CARDS_WITH_ENTITY = frozenset(
    {
        "alarm-panel",
        "alert",
        "button",
        "entity",
        "entity-button",
        "gauge",
        "humidifier",
        "light",
        "media-control",
        "picture-elements",
        "picture-entity",
        "picture-glance",
        "plant-status",
        "sensor",
        "thermostat",
        "tile",
        "todo-list",
        "weather-forecast",
    }
)

# Core cards whose `entities` lists entity IDs, as a string or as the `entity`
# of a row. Not the statistics graph, for the same reason as the statistic
# card. The logbook card has its own rules, further down.
_CARDS_WITH_ENTITIES = frozenset(
    {
        "calendar",
        "distribution",
        "entities",
        "entity-filter",
        "glance",
        "history-graph",
        "map",
        "picture-glance",
        "toggle-group",
    }
)

# The heading card lists its badges under `badges`, and under `entities`
# before that. A badge without a type is an entity badge.
_HEADING_CARD = "heading"
_HEADING_BADGE_KEYS = ("badges", "entities")

# The picture elements that name an entity, and the one that holds more.
_PICTURE_ELEMENTS_CARD = "picture-elements"
_ELEMENTS_WITH_ENTITY = frozenset(
    {"icon", "image", "state-badge", "state-icon", "state-label"}
)
_CONDITIONAL_ELEMENT = "conditional"

# View badges. A string is an entity badge, and so is one without a type.
_BADGES_WITH_ENTITY = frozenset({"entity", "state-label"})
_BADGES_WITH_ENTITIES = frozenset({"entity-filter"})
_ENTITY_BADGE = "entity"

# The view types. Anything else handed over on its own is a card.
_VIEW_TYPES = frozenset({"masonry", "panel", "sections", "sidebar"})

_CUSTOM_PREFIX = "custom:"

# Filled in by something before the card ever sees it: Jinja, button-card's
# `[[[ ]]]`, decluttering-card's `[[entity]]`. No entity ID has a brace or a
# bracket in it, so neither is one that is wrong.
_FILLED_IN_LATER = ("{", "[")


def _is_not_an_entity_id(value: str) -> bool:
    """Return whether a value in an entity field is no entity ID at all.

    An entity ID with capitals is one, and reported as written elsewhere.
    Everything the entity walk lets go on purpose is let go here too.
    """
    lower_cased = value.lower()
    return not (
        # Left empty by an editor halfway through.
        not value.strip()
        or valid_entity_id(lower_cased)
        or lower_cased in (ENTITY_MATCH_ALL, ENTITY_MATCH_NONE)
        or lower_cased.startswith(NEVER_AN_ENTITY_PREFIXES)
        or value.startswith(IGNORED_ENTITY_DOMAINS)
        or value in _CARD_PLACEHOLDERS
        or is_pattern_reference(value)
        or any(mark in value for mark in _FILLED_IN_LATER)
    )


def _check_value(value: Any, found: set[str]) -> None:
    """Collect a field's value if it is no entity ID."""
    if not isinstance(value, str):
        return

    found.update(
        item
        for item in split_comma_separated_entity_ids(value)
        if _is_not_an_entity_id(item)
    )


def _is_custom(node: dict[str, Any]) -> bool:
    """Return whether a dashboard node is a custom one."""
    return isinstance(node_type := node.get("type"), str) and node_type.startswith(
        _CUSTOM_PREFIX
    )


def _check_entity_list(items: Any, found: set[str]) -> None:
    """Collect what in an `entities` list is no entity ID."""
    if not isinstance(items, list):
        return

    for item in items:
        if isinstance(item, str):
            _check_value(item, found)
        elif isinstance(item, dict) and not _is_custom(item):
            _check_value(item.get("entity"), found)


def _check_logbook_card(card: dict[str, Any], found: set[str]) -> None:
    """Collect what a logbook card filters on that is no entity ID.

    Held to the same rule as the entity walk: only under a domain Home
    Assistant knows, since anything else is an ID somebody made up for their
    own entries.
    """
    candidates: set[str] = set()
    _check_entity_list(card.get("entities"), candidates)

    if isinstance(target := card.get("target"), dict):
        entity_ids = target.get("entity_id")
        for entity_id in entity_ids if isinstance(entity_ids, list) else [entity_ids]:
            _check_value(entity_id, candidates)

    found.update(
        value
        for value in candidates
        if value.partition(".")[0].lower() in KNOWN_DOMAINS
    )


def _check_badges(badges: Any, found: set[str]) -> None:
    """Collect what a view's badges name that is no entity ID."""
    if not isinstance(badges, list):
        return

    for badge in badges:
        if isinstance(badge, str):
            _check_value(badge, found)
            continue

        if not isinstance(badge, dict):
            continue

        # Checked for a string first: a list or a dict cannot be looked up in
        # a set.
        if not isinstance(badge_type := badge.get("type", _ENTITY_BADGE), str):
            continue

        if badge_type in _BADGES_WITH_ENTITY:
            _check_value(badge.get("entity"), found)
        elif badge_type in _BADGES_WITH_ENTITIES:
            _check_entity_list(badge.get("entities"), found)


def _check_heading_badges(card: dict[str, Any], found: set[str]) -> None:
    """Collect what a heading card's badges name that is no entity ID."""
    for key in _HEADING_BADGE_KEYS:
        if not isinstance(badges := card.get(key), list):
            continue

        for badge in badges:
            if isinstance(badge, dict) and badge.get("type", _ENTITY_BADGE) == (
                _ENTITY_BADGE
            ):
                _check_value(badge.get("entity"), found)


def _check_elements(elements: Any, found: set[str]) -> None:
    """Collect what picture elements name that is no entity ID."""
    if not isinstance(elements, list):
        return

    for element in elements:
        if not isinstance(element, dict):
            continue

        if not isinstance(element_type := element.get("type"), str):
            continue

        if element_type in _ELEMENTS_WITH_ENTITY:
            _check_value(element.get("entity"), found)
        elif element_type == _CONDITIONAL_ELEMENT:
            _check_elements(element.get("elements"), found)


def _check_card(card: Any, found: set[str]) -> None:
    """Collect what a core card, and the cards in it, name that is no entity ID."""
    if not isinstance(card, dict) or not isinstance(card_type := card.get("type"), str):
        return

    # Nor what a custom card holds: a stack of its own may hand its cards to
    # the frontend as they are, or fill them in first.
    if card_type.startswith(_CUSTOM_PREFIX):
        return

    if card_type in _CARDS_WITH_ENTITY:
        _check_value(card.get("entity"), found)
    if card_type in _CARDS_WITH_ENTITIES:
        _check_entity_list(card.get("entities"), found)
    if card_type == _LOGBOOK_CARD_TYPE:
        _check_logbook_card(card, found)
    if card_type == _HEADING_CARD:
        _check_heading_badges(card, found)
    if card_type == _PICTURE_ELEMENTS_CARD:
        _check_elements(card.get("elements"), found)

    # The stacks and the grid hold cards, the conditional and the entity
    # filter card hold one.
    _check_cards(card.get("cards"), found)
    _check_card(card.get("card"), found)


def _check_cards(cards: Any, found: set[str]) -> None:
    """Collect what a list of cards names that is no entity ID."""
    if not isinstance(cards, list):
        return

    for card in cards:
        _check_card(card, found)


def _check_view(view: dict[str, Any], found: set[str]) -> None:
    """Collect what a view's cards and badges name that is no entity ID."""
    if _is_custom(view):
        return

    _check_badges(view.get("badges"), found)

    sections = view.get("sections")
    for section in sections if isinstance(sections, list) else []:
        if isinstance(section, dict) and not _is_custom(section):
            _check_cards(section.get("cards"), found)

    _check_cards(view.get("cards"), found)


def extract_not_entity_ids_from_dashboard_node(node: Any) -> set[str]:
    """Return what a core card's entity field holds that is no entity ID.

    Accepts a whole dashboard, a view or a single card. Only the core cards,
    and only their fields that take an entity ID and nothing else.
    """
    found: set[str] = set()

    if isinstance(node, list):
        for item in node:
            found |= extract_not_entity_ids_from_dashboard_node(item)
        return found

    if not isinstance(node, dict):
        return found

    if isinstance(views := node.get("views"), list):
        for view in views:
            if isinstance(view, dict):
                _check_view(view, found)
    elif not isinstance(node_type := node.get("type"), str) or node_type in _VIEW_TYPES:
        _check_view(node, found)
    else:
        _check_card(node, found)

    return found


# `area` is a reference on exactly two things, the area card and the area
# view strategy, and both say `type: area`. Anywhere else the word is up for
# grabs, and a custom card took it: flex-horseshoe-card prints whatever is
# under `area` as a caption beneath its gauge, so `area: Garaj` was reported
# as an area that had gone missing. #1609.
#
# The Mushroom template card is the exception that earns its place: its `area`
# is the card's area, handed to its templates as a real area ID.
_AREA_TYPES = frozenset({"area", "custom:mushroom-template-card"})

# `area_id` is a service-call target, and nobody captions with one of those.
_AREA_ID_KEY = "area_id"


def _collect_plain(value: Any, out: set[str]) -> None:
    """Collect plain string IDs from a key's string or list value.

    A pattern is not a name, so `area: KG/*` is left where it is. Neither is
    a template: no area ID has braces in it, and what a template turns into
    is not something to look up ahead of time.
    """
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list):
        return

    out.update(
        item
        for item in values
        if isinstance(item, str)
        and not is_pattern_reference(item)
        and not _is_template(item)
    )


def _is_template(value: str) -> bool:
    """Return whether a value is a Jinja template rather than a name."""
    return "{{" in value or "{%" in value


def _walk_areas(node: Any, areas: set[str]) -> None:
    """Recursively collect area references from a configuration node."""
    if isinstance(node, list):
        for item in node:
            _walk_areas(item, areas)
        return

    if not isinstance(node, dict):
        return

    # Checked for a string first: the walk goes into any dict in a dashboard,
    # and a `type` that is a list or a dict cannot be looked up in a set.
    if isinstance(card_type := node.get("type"), str) and card_type in _AREA_TYPES:
        _collect_plain(node.get("area"), areas)
    _collect_plain(node.get(_AREA_ID_KEY), areas)

    # The areas dashboard strategy lists area IDs to hide or order.
    if isinstance(areas_display := node.get("areas_display"), dict):
        for sub_key in ("hidden", "order"):
            _collect_plain(areas_display.get(sub_key), areas)

    # And keys its per-area options by area ID.
    _collect_plain(list(_areas_options(node)), areas)

    for child in _worth_descending_into(node):
        _walk_areas(child, areas)


def extract_areas_from_dashboard_node(node: Any) -> set[str]:
    """Return the area references found anywhere in a dashboard node."""
    areas: set[str] = set()
    _walk_areas(node, areas)
    return areas


# The two kinds of action that call one. `call-service` is the old name for
# `perform-action`, and the frontend runs both the same way: the action named
# under `perform_action`, or failing that under `service`. Read exactly like
# that, so what is reported is what a tap would have tried to run.
_PERFORM_ACTION_TYPES = frozenset({"perform-action", "call-service"})
_PERFORM_ACTION_KEYS = ("perform_action", "service")

# What `||` in JavaScript passes over. Not Python's idea of empty: an empty
# list or dict is truthy over there, so the frontend stops at it and never
# gets to `service`. Compared with `==`, which keeps an unhashable value out
# of trouble and lets `0.0` count as the `0` it is.
_JAVASCRIPT_FALSY = (None, "", 0, False)

# Only a plain `domain.action` is a name to look up. A custom card can put a
# template there, button-card's `[[[ ... ]]]` for one, and a half-filled
# editor leaves it empty; neither is an action that went missing.
_ACTION_NAME = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+")

# Some cards borrow the frontend's action shape for actions they run in the
# browser themselves. ha-floorplan's `floorplan.style_set`, `floorplan.class_set`
# and the rest never reach Home Assistant, so there is nothing to find missing.
# Only inside that card, though: anywhere else nothing would run them, and an
# action nobody runs is exactly what this repair is for.
_CARD_OWN_ACTION_DOMAINS = {"custom:floorplan-card": "floorplan"}

# The picture-elements card's button element names its action at the top
# level, not in a tap action: under `action`, or failing that the older
# `service`. Only on that element, since a bare `service` anywhere else is
# whatever the card says it is. The frontend reads `action ?? service`, so only
# a missing `action` falls through. `action-button` is the name its editor
# gives a new one, and the frontend builds it as the same element.
_BUTTON_ELEMENT_TYPES = frozenset({"service-button", "action-button"})

# The entities card's call-service row names its action at the top level too,
# but reads it as `action || service`, so an empty `action` falls through as
# well. It turns that into a tap action, which a `tap_action` of the row's own
# replaces outright, and a row without a `name` is an error card: neither one
# runs it. The entities card hands a `perform-action` row over as this one.
#
# Only read in the rows of an entities card, the one place the frontend builds
# them, and in a conditional row's `row` there. That one goes to the frontend
# as is, so only under its own name. The same shape anywhere else is whatever
# that card says it is.
_ENTITIES_CARD = "entities"
_CALL_SERVICE_ROW_TYPES = frozenset({"call-service", "perform-action"})
_CALL_SERVICE_ROW_TYPE = "call-service"
_CONDITIONAL_ROW_TYPE = "conditional"


def _collect_action(name: Any, actions: set[str], card_domain: str | None) -> None:
    """Collect an action name, if it is one to look up."""
    if (
        isinstance(name, str)
        and _ACTION_NAME.fullmatch(name)
        and name.split(".", 1)[0] != card_domain
    ):
        actions.add(name)


def _button_element_action(node: dict[str, Any]) -> Any:
    """Return what a button element names as its action."""
    if (name := node.get("action")) is not None:
        return name
    return node.get("service")


def _call_service_row_action(node: dict[str, Any]) -> Any:
    """Return what a call-service row performs, if it performs anything."""
    if "tap_action" in node or node.get("name") in _JAVASCRIPT_FALSY:
        return None
    if (name := node.get("action")) not in _JAVASCRIPT_FALSY:
        return name
    return node.get("service")


def _call_service_rows(card: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield the rows of an entities card the frontend builds as call-service."""
    if not isinstance(rows := card.get("entities"), list):
        return

    for row in rows:
        if not isinstance(row, dict) or not isinstance(
            row_type := row.get("type"), str
        ):
            continue

        if row_type in _CALL_SERVICE_ROW_TYPES:
            yield row
        elif (
            row_type == _CONDITIONAL_ROW_TYPE
            and isinstance(inner := row.get("row"), dict)
            and inner.get("type") == _CALL_SERVICE_ROW_TYPE
        ):
            yield inner


def _top_level_actions(node: dict[str, Any], card_type: str) -> Iterator[Any]:
    """Yield the actions a node names outside a tap action, if it is that kind."""
    if card_type in _BUTTON_ELEMENT_TYPES:
        yield _button_element_action(node)
    elif card_type == _ENTITIES_CARD:
        for row in _call_service_rows(node):
            yield _call_service_row_action(row)


def _walk_actions(node: Any, actions: set[str], card_domain: str | None = None) -> None:
    """Recursively collect the actions a configuration node performs.

    `card_domain` is the domain of the actions the enclosing card runs itself.
    """
    if isinstance(node, list):
        for item in node:
            _walk_actions(item, actions, card_domain)
        return

    if not isinstance(node, dict):
        return

    if isinstance(card_type := node.get("type"), str):
        card_domain = _CARD_OWN_ACTION_DOMAINS.get(card_type, card_domain)

        for name in _top_level_actions(node, card_type):
            _collect_action(name, actions, card_domain)

    # Read off the action itself rather than the key it sits under:
    # `tap_action`, `hold_action` and the rest are the frontend's, and custom
    # cards add their own names for the same shape. Checked for a string
    # first, like the area walk: a list or a dict cannot be looked up in a set.
    if (
        isinstance(action_type := node.get("action"), str)
        and action_type in _PERFORM_ACTION_TYPES
    ):
        for key in _PERFORM_ACTION_KEYS:
            if (name := node.get(key)) in _JAVASCRIPT_FALSY:
                continue
            _collect_action(name, actions, card_domain)
            break

    for child in _worth_descending_into(node):
        _walk_actions(child, actions, card_domain)


def extract_actions_from_dashboard_node(node: Any) -> set[str]:
    """Return the actions performed anywhere in a dashboard node."""
    actions: set[str] = set()
    _walk_actions(node, actions)
    return actions
