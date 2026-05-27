"""Golden-path tests for the Lovelace entity-reference extractor.

The dashboard walker in
``custom_components/spook/ectoplasms/lovelace/repairs/unknown_entity_references.py``
is the only place where Spook converts Lovelace YAML into a flat set of entity
IDs. These tests pin down its current behavior so the upcoming flattening into a
single recursive walker cannot regress it silently.

The extraction methods are name-mangled private methods on ``SpookRepair``;
tests call them through the mangled attribute names, which is intentional — the
mission says "lock down the riskiest logic before any refactor".
"""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.spook.ectoplasms.lovelace.repairs.unknown_entity_references import (
    SpookRepair,
)
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture(name="repair")
def repair_fixture(hass: HomeAssistant) -> SpookRepair:
    """Return a ``SpookRepair`` instance wired up to the test ``hass``."""
    return SpookRepair(hass)


def _extract(repair: SpookRepair, config: dict[str, Any]) -> set[str]:
    """Call the name-mangled dashboard-level extractor."""
    return repair._SpookRepair__async_extract_entities(config)  # noqa: SLF001  # type: ignore[attr-defined]


def _extract_card(repair: SpookRepair, config: dict[str, Any]) -> set[str]:
    """Call the name-mangled card-level extractor."""
    return repair._SpookRepair__async_extract_entities_from_card(config)  # noqa: SLF001  # type: ignore[attr-defined]


def _extract_badge(repair: SpookRepair, config: Any) -> set[str]:
    """Call the name-mangled badge-level extractor."""
    return repair._SpookRepair__async_extract_entities_from_badge(config)  # noqa: SLF001  # type: ignore[attr-defined]


def _extract_element(repair: SpookRepair, config: dict[str, Any]) -> set[str]:
    """Call the name-mangled element-level extractor."""
    return repair._SpookRepair__async_extract_entities_from_element(config)  # noqa: SLF001  # type: ignore[attr-defined]


def test_dashboard_with_no_views_returns_empty(repair: SpookRepair) -> None:
    """A dashboard with no ``views`` key yields no entities."""
    assert _extract(repair, {}) == set()


def test_dashboard_non_dict_returns_empty(repair: SpookRepair) -> None:
    """A non-dict config yields no entities."""
    assert _extract(repair, "not a dict") == set()  # type: ignore[arg-type]


def test_dashboard_full_walk(repair: SpookRepair) -> None:
    """Views, badges, cards, and sections are all walked."""
    config = {
        "views": [
            {
                "title": "Home",
                "badges": [{"entity": "sensor.outside_temperature"}],
                "cards": [{"type": "entity", "entity": "light.kitchen"}],
                "sections": [{"cards": [{"type": "entity", "entity": "switch.lamp"}]}],
            }
        ]
    }
    assert _extract(repair, config) == {
        "sensor.outside_temperature",
        "light.kitchen",
        "switch.lamp",
    }


def test_card_single_entity_field(repair: SpookRepair) -> None:
    """A card with a plain ``entity`` field is captured."""
    assert _extract_card(repair, {"type": "entity", "entity": "light.kitchen"}) == {
        "light.kitchen"
    }


def test_card_entities_list_mixed_forms(repair: SpookRepair) -> None:
    """A card's ``entities`` list accepts strings and ``{"entity": ...}`` dicts."""
    config = {
        "type": "entities",
        "entities": [
            "light.kitchen",
            {"entity": "switch.lamp"},
            {"entity": "sensor.temperature", "name": "Temp"},
        ],
    }
    assert _extract_card(repair, config) == {
        "light.kitchen",
        "switch.lamp",
        "sensor.temperature",
    }


def test_card_camera_image(repair: SpookRepair) -> None:
    """The ``camera_image`` common field is captured."""
    assert _extract_card(
        repair, {"type": "picture-entity", "camera_image": "camera.front"}
    ) == {"camera.front"}


def test_card_nested_card_and_cards(repair: SpookRepair) -> None:
    """``card`` (single) and ``cards`` (list) are both walked."""
    config = {
        "type": "conditional",
        "card": {"type": "entity", "entity": "light.kitchen"},
        "cards": [
            {"type": "entity", "entity": "switch.lamp"},
            {"type": "entity", "entity": "sensor.temperature"},
        ],
    }
    assert _extract_card(repair, config) == {
        "light.kitchen",
        "switch.lamp",
        "sensor.temperature",
    }


def test_card_tap_action_target(repair: SpookRepair) -> None:
    """A ``tap_action`` with a target entity is captured."""
    config = {
        "type": "button",
        "tap_action": {
            "action": "call-service",
            "service": "light.toggle",
            "target": {"entity_id": "light.kitchen"},
        },
    }
    assert _extract_card(repair, config) == {"light.kitchen"}


def test_card_hold_action_service_data(repair: SpookRepair) -> None:
    """A ``hold_action`` with service_data entities is captured."""
    config = {
        "type": "button",
        "hold_action": {
            "action": "call-service",
            "service": "light.turn_on",
            "service_data": {"entity_id": ["light.kitchen", "light.living_room"]},
        },
    }
    assert _extract_card(repair, config) == {
        "light.kitchen",
        "light.living_room",
    }


def test_card_condition_entity(repair: SpookRepair) -> None:
    """A card's ``condition.entity`` is captured."""
    config = {
        "type": "conditional",
        "condition": {"entity": "input_boolean.guest", "state": "on"},
        "card": {"type": "entity", "entity": "light.kitchen"},
    }
    assert _extract_card(repair, config) == {
        "input_boolean.guest",
        "light.kitchen",
    }


def test_card_visibility_conditions(repair: SpookRepair) -> None:
    """A card's ``visibility`` list of conditions is captured."""
    config = {
        "type": "entity",
        "entity": "light.kitchen",
        "visibility": [
            {"condition": "state", "entity": "input_boolean.guest", "state": "on"},
        ],
    }
    assert _extract_card(repair, config) == {
        "light.kitchen",
        "input_boolean.guest",
    }


def test_card_header_and_footer(repair: SpookRepair) -> None:
    """Header and footer common fields are captured."""
    config = {
        "type": "entities",
        "header": {"type": "picture", "camera_image": "camera.front"},
        "footer": {"type": "graph", "entity": "sensor.power"},
        "entities": ["light.kitchen"],
    }
    assert _extract_card(repair, config) == {
        "camera.front",
        "sensor.power",
        "light.kitchen",
    }


def test_card_picture_elements_walked(repair: SpookRepair) -> None:
    """``elements`` on a picture-elements card are walked into."""
    config = {
        "type": "picture-elements",
        "elements": [
            {"type": "state-icon", "entity": "light.kitchen"},
            {
                "type": "service-button",
                "tap_action": {
                    "action": "call-service",
                    "service": "switch.toggle",
                    "target": {"entity_id": "switch.lamp"},
                },
            },
        ],
    }
    assert _extract_card(repair, config) == {"light.kitchen", "switch.lamp"}


def test_card_mushroom_chips(repair: SpookRepair) -> None:
    """``chips`` on a mushroom chips card are walked and conditions captured."""
    config = {
        "type": "custom:mushroom-chips-card",
        "chips": [
            {"type": "entity", "entity": "sensor.temperature"},
            {
                "type": "template",
                "entity": "switch.lamp",
                "conditions": [
                    {"entity": "input_boolean.guest"},
                ],
            },
        ],
    }
    assert _extract_card(repair, config) == {
        "sensor.temperature",
        "switch.lamp",
        "input_boolean.guest",
    }


def test_card_non_dict_returns_empty(repair: SpookRepair) -> None:
    """A non-dict card config returns an empty set."""
    assert _extract_card(repair, "string-card") == set()  # type: ignore[arg-type]


def test_badge_string_form(repair: SpookRepair) -> None:
    """A bare string badge is treated as the entity itself."""
    assert _extract_badge(repair, "sensor.temperature") == {"sensor.temperature"}


def test_badge_entity_dict(repair: SpookRepair) -> None:
    """A badge with an ``entity`` field is captured."""
    assert _extract_badge(repair, {"entity": "sensor.temperature"}) == {
        "sensor.temperature"
    }


def test_badge_entities_list(repair: SpookRepair) -> None:
    """A badge with an ``entities`` list captures all forms."""
    config = {
        "entities": [
            "sensor.a",
            {"entity": "sensor.b"},
        ]
    }
    assert _extract_badge(repair, config) == {"sensor.a", "sensor.b"}


def test_badge_unknown_shape_returns_empty(repair: SpookRepair) -> None:
    """An unrecognized badge shape yields an empty set."""
    assert _extract_badge(repair, {"foo": "bar"}) == set()
    assert _extract_badge(repair, 42) == set()


def test_element_with_nested_elements(repair: SpookRepair) -> None:
    """``elements`` nested inside an element are walked recursively."""
    config = {
        "type": "state-badge",
        "entity": "sensor.outside",
        "elements": [
            {"type": "state-icon", "entity": "light.kitchen"},
        ],
    }
    assert _extract_element(repair, config) == {
        "sensor.outside",
        "light.kitchen",
    }


def test_element_with_visibility(repair: SpookRepair) -> None:
    """An element's ``visibility`` conditions contribute entities."""
    config = {
        "type": "state-icon",
        "entity": "light.kitchen",
        "visibility": [
            {"condition": "state", "entity": "input_boolean.guest", "state": "on"},
        ],
    }
    assert _extract_element(repair, config) == {
        "light.kitchen",
        "input_boolean.guest",
    }


def test_element_action_target(repair: SpookRepair) -> None:
    """An element acting as its own action (``service_data``) contributes."""
    config = {
        "type": "service-button",
        "service": "switch.toggle",
        "service_data": {"entity_id": "switch.lamp"},
    }
    assert _extract_element(repair, config) == {"switch.lamp"}


def test_element_non_dict_returns_empty(repair: SpookRepair) -> None:
    """A non-dict element returns an empty set."""
    assert _extract_element(repair, "not a dict") == set()  # type: ignore[arg-type]
