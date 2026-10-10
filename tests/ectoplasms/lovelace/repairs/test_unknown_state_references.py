"""Tests for the Lovelace unknown state references repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from homeassistant.components.light import LightEntity
from homeassistant.components.switch import SwitchEntity

from custom_components.spook.draft_checking import async_check_draft
from custom_components.spook.ectoplasms.lovelace.repairs.unknown_state_references import (
    SpookRepair,
)
from tests.entity_objects import give_entity_objects
from tests.ectoplasms.lovelace.repairs.dashboard_helpers import (
    async_assert_waits_for_the_recorder,
    dashboard,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "lovelace_unknown_state_references_lovelace"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_db_url: str,
    enable_custom_integrations: None,
) -> None:
    """Prepare the recorder's database before Home Assistant starts."""
    _ = recorder_db_url, enable_custom_integrations


async def _states_found(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, *cards: Any, **view: Any
) -> str | None:
    """Inspect a dashboard with these cards, and return the states reported."""
    repair = SpookRepair(hass)
    repair._dashboards = {"lovelace": dashboard(*cards, **view)}  # noqa: SLF001
    await repair.async_inspect()

    if (issue := async_issue_about(issue_registry, ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["states"]


def _kitchen_light(hass: HomeAssistant) -> None:
    """Make a light its domain holds, which is off right now."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "off")


def _visible_when(**condition: Any) -> dict[str, Any]:
    """Return a card shown only when a condition passes."""
    return {
        "type": "button",
        "entity": "light.kitchen",
        "visibility": [condition],
    }


async def test_visibility_condition_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a visibility condition checking a state never had is reported."""
    _kitchen_light(hass)

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": dashboard(
            _visible_when(condition="state", entity="light.kitchen", state="On")
        )
    }
    await repair.async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "lovelace_unknown_state_references"
    assert issue.translation_placeholders == {
        "dashboard": "Overview",
        "edit": "/lovelace/kitchen?edit=1",
        "states": "- `On` for `light.kitchen` (did you mean `on`?)",
    }


async def test_known_state_is_fine(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a state the entity can be in is not reported."""
    _kitchen_light(hass)

    assert (
        await _states_found(
            hass,
            issue_registry,
            _visible_when(condition="state", entity="light.kitchen", state="on"),
        )
        is None
    )


@pytest.mark.parametrize(
    "condition",
    [
        # Nested in every logical condition, `conditions` a list or one.
        {
            "condition": "or",
            "conditions": [
                {
                    "condition": "and",
                    "conditions": {"entity": "light.kitchen", "state": "On"},
                }
            ],
        },
        {
            "condition": "not",
            "conditions": [{"entity": "light.kitchen", "state": "On"}],
        },
        # `state_not` when there is no `state`.
        {"condition": "state", "entity": "light.kitchen", "state_not": "On"},
        # The core shape, with `entity_id`.
        {"condition": "state", "entity_id": "light.kitchen", "state": ["off", "On"]},
        # The old shape, without `condition`.
        {"entity": "light.kitchen", "state": "On"},
        # No entity: the card's own.
        {"condition": "state", "state": "On"},
        # An empty `entity_id` falls through to `entity`, like `||` does.
        {
            "condition": "state",
            "entity_id": "",
            "entity": "light.kitchen",
            "state": "On",
        },
    ],
)
async def test_every_condition_shape_is_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, condition: dict[str, Any]
) -> None:
    """Test each way the frontend reads a state condition is read the same."""
    _kitchen_light(hass)

    found = await _states_found(
        hass,
        issue_registry,
        {"type": "button", "entity": "light.kitchen", "visibility": [condition]},
    )

    assert found == "- `On` for `light.kitchen` (did you mean `on`?)"


@pytest.mark.parametrize(
    "condition",
    [
        # `state` goes first; `state_not` is not looked at then.
        {
            "condition": "state",
            "entity": "light.kitchen",
            "state": "on",
            "state_not": "On",
        },
        # With an attribute, the value is that attribute's.
        {
            "condition": "state",
            "entity": "light.kitchen",
            "attribute": "color_mode",
            "state": "On",
        },
        # Switched off, or switched by a template only core can read.
        {
            "condition": "state",
            "entity": "light.kitchen",
            "state": "On",
            "enabled": False,
        },
        {
            "condition": "state",
            "entity": "light.kitchen",
            "state": "On",
            "enabled": "{{ true }}",
        },
        # Templates and placeholders are worked out while running.
        {"condition": "state", "entity": "light.kitchen", "state": "{{ 'On' }}"},
        {
            "condition": "state",
            "entity": "light.kitchen",
            "state": "[[[ return 'On' ]]]",
        },
        {"condition": "state", "entity": "light.kitchen", "state": "${'On'}"},
        # Two different entities: old frontends read `entity`, new ones
        # `entity_id`.
        {
            "condition": "state",
            "entity_id": "light.kitchen",
            "entity": "light.hallway",
            "state": "On",
        },
        # Not a state condition at all.
        {"condition": "numeric_state", "entity": "light.kitchen", "above": "On"},
        {
            "condition": "template",
            "value_template": "{{ is_state('light.kitchen', 'On') }}",
        },
    ],
)
async def test_what_the_frontend_does_not_compare_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, condition: dict[str, Any]
) -> None:
    """Test a condition that does not compare with that state is not judged."""
    _kitchen_light(hass)

    assert (
        await _states_found(
            hass,
            issue_registry,
            {"type": "button", "entity": "light.kitchen", "visibility": [condition]},
        )
        is None
    )


async def test_section_hands_nothing_to_its_conditions(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a section's conditions never take an entity, whatever it says."""
    _kitchen_light(hass)
    section = {
        "type": "grid",
        "entity": "light.kitchen",
        "cards": [],
        "visibility": [{"condition": "state", "state": "On"}],
    }

    assert await _states_found(hass, issue_registry, sections=[section]) is None


async def test_conditional_card_hands_nothing_to_its_conditions(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the conditional card's conditions never take an entity."""
    _kitchen_light(hass)
    card = {
        "type": "conditional",
        "entity": "light.kitchen",
        "conditions": [{"condition": "state", "state": "On"}],
        "card": {"type": "tile", "entity": "light.kitchen"},
    }

    assert await _states_found(hass, issue_registry, card) is None


@pytest.mark.parametrize(
    "card",
    [
        {
            "type": "conditional",
            "conditions": [{"entity": "light.kitchen", "state": "On"}],
            "card": {"type": "tile", "entity": "light.kitchen"},
        },
        {
            "type": "entities",
            "entities": [
                {
                    "type": "conditional",
                    "conditions": [{"entity": "light.kitchen", "state_not": "On"}],
                    "row": {"entity": "light.kitchen"},
                }
            ],
        },
        {
            "type": "picture-elements",
            "image": "/local/floorplan.png",
            "elements": [
                {
                    "type": "conditional",
                    "conditions": [
                        {"condition": "state", "entity": "light.kitchen", "state": "On"}
                    ],
                    "elements": [],
                }
            ],
        },
        # The image of a picture card, picked by state.
        {
            "type": "picture-entity",
            "entity": "light.kitchen",
            "state_image": {"on": "/local/on.png", "On": "/local/oops.png"},
        },
        {
            "type": "picture-elements",
            "image": "/local/floorplan.png",
            "elements": [
                {
                    "type": "image",
                    "entity": "light.kitchen",
                    "state_filter": {"On": "brightness(110%)"},
                }
            ],
        },
        # A heading badge hands its entity to its own conditions.
        {
            "type": "heading",
            "badges": [
                {
                    "entity": "light.kitchen",
                    "visibility": [{"condition": "state", "state": "On"}],
                }
            ],
        },
    ],
)
async def test_every_place_a_state_is_compared_is_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, card: dict[str, Any]
) -> None:
    """Test the conditional cards, rows, elements and state pictures are read."""
    _kitchen_light(hass)

    found = await _states_found(hass, issue_registry, card)

    assert found == "- `On` for `light.kitchen` (did you mean `on`?)"


@pytest.mark.parametrize(
    "card",
    [
        {
            "type": "custom:button-card",
            "entity": "light.kitchen",
            "visibility": [{"condition": "state", "state": "On"}],
        },
        {
            "type": "custom:stack-in-card",
            "cards": [_visible_when(condition="state", state="On")],
        },
    ],
)
async def test_custom_cards_are_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, card: dict[str, Any]
) -> None:
    """Test a custom card, and anything inside one, is never judged."""
    _kitchen_light(hass)

    assert await _states_found(hass, issue_registry, card) is None


async def test_entity_that_does_not_exist_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a missing entity is the unknown entity repair's business."""
    _kitchen_light(hass)

    assert (
        await _states_found(
            hass,
            issue_registry,
            _visible_when(condition="state", entity="light.gone", state="On"),
        )
        is None
    )


def _entity_filter(*entities: Any, **filters: Any) -> dict[str, Any]:
    """Return an entity filter card."""
    return {"type": "entity-filter", "entities": list(entities), **filters}


async def test_shared_filter_is_reported_when_no_entity_can_pass(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a filter for all entities, that none of them can ever pass."""
    _kitchen_light(hass)
    give_entity_objects(hass, "switch.kettle", kind=SwitchEntity)
    hass.states.async_set("switch.kettle", "off")

    found = await _states_found(
        hass,
        issue_registry,
        _entity_filter("light.kitchen", "switch.kettle", state_filter=["On"]),
    )

    assert found == (
        "- `On` for `light.kitchen` (did you mean `on`?)\n"
        "- `On` for `switch.kettle` (did you mean `on`?)"
    )


async def test_shared_filter_one_entity_can_pass_is_fine(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a filter is fine as long as one of its entities can pass it.

    A sensor can be in any state, so `On` is something it might well be.
    """
    _kitchen_light(hass)
    hass.states.async_set("sensor.mode", "On")

    assert (
        await _states_found(
            hass,
            issue_registry,
            _entity_filter(
                "light.kitchen",
                "sensor.mode",
                conditions=[{"condition": "state", "state": "On"}],
            ),
        )
        is None
    )


@pytest.mark.parametrize(
    "card",
    [
        # Its own filter.
        _entity_filter({"entity": "light.kitchen", "state_filter": ["On"]}),
        _entity_filter(
            {
                "entity": "light.kitchen",
                "state_filter": [{"operator": "==", "value": "On"}],
            }
        ),
        _entity_filter(
            {
                "entity": "light.kitchen",
                "state_filter": [{"operator": "not in", "value": ["off", "On"]}],
            }
        ),
        _entity_filter(
            {
                "entity": "light.kitchen",
                "conditions": [{"condition": "state", "state": "On"}],
            }
        ),
    ],
)
async def test_entity_filter_shapes_are_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, card: dict[str, Any]
) -> None:
    """Test each shape of an entity filter is read."""
    _kitchen_light(hass)

    found = await _states_found(hass, issue_registry, card)

    assert found == "- `On` for `light.kitchen` (did you mean `on`?)"


@pytest.mark.parametrize(
    "card",
    [
        # Text with `in` is a substring check.
        _entity_filter(
            {
                "entity": "light.kitchen",
                "state_filter": [{"operator": "in", "value": "On"}],
            }
        ),
        # Compared by order or pattern, or not at all.
        _entity_filter(
            {
                "entity": "light.kitchen",
                "state_filter": [{"operator": "regex", "value": "On"}],
            }
        ),
        _entity_filter({"entity": "light.kitchen", "state_filter": [{"value": "On"}]}),
        # The value of an attribute.
        _entity_filter(
            {
                "entity": "light.kitchen",
                "state_filter": [
                    {"operator": "==", "attribute": "mode", "value": "On"}
                ],
            }
        ),
        # The card takes its own state filter, the badge the conditions.
        _entity_filter(
            {"entity": "light.kitchen", "state_filter": ["On"]},
            conditions=[{"condition": "state", "state": "On"}],
        ),
    ],
)
async def test_entity_filter_not_comparing_the_state_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, card: dict[str, Any]
) -> None:
    """Test a filter that does not compare with the state as written is not read."""
    _kitchen_light(hass)

    assert await _states_found(hass, issue_registry, card) is None


async def _recorded_kitchen_light(hass: HomeAssistant) -> None:
    """Make a light the recorder has the whole history of: on, then off."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("light.kitchen", "off")
    await async_wait_recording_done(hass)


@pytest.mark.usefixtures("recorder_mock")
async def test_state_never_had_is_reported_from_history(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a state outside of the set is reported with the whole history."""
    await _recorded_kitchen_light(hass)

    found = await _states_found(
        hass,
        issue_registry,
        _visible_when(condition="state", entity="light.kitchen", state="dimmed"),
    )

    assert found == "- `dimmed` for `light.kitchen`"


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "condition",
    [
        # Compared with the state of that entity too, whatever its domain.
        {"condition": "state", "entity": "light.kitchen", "state": "sensor.wanted"},
        {"entity": "light.kitchen", "state_not": ["off", "select.Mode"]},
        # A missing entity evaluates as unknown, and every entity can be
        # unknown or unavailable.
        {
            "condition": "state",
            "entity": "light.kitchen",
            "state": ["unknown", "unavailable"],
        },
        # What YAML hands over as a number or true is not text, and the
        # frontend and core compare those differently.
        {"condition": "state", "entity": "light.kitchen", "state": 0},
        {"condition": "state", "entity": "light.kitchen", "state": True},
        {"condition": "state", "entity": "light.kitchen", "state": [1, False]},
        # Placeholders of the cards that run JavaScript, and Jinja.
        {
            "condition": "state",
            "entity": "light.kitchen",
            "state": "[[[ return 'x' ]]]",
        },
        {"condition": "state", "entity": "light.kitchen", "state": "${state}"},
        {"condition": "state", "entity": "light.kitchen", "state": "{{ 'x' }}"},
    ],
)
async def test_values_the_frontend_does_not_compare_as_written_are_fine(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, condition: dict[str, Any]
) -> None:
    """Test values that are not a written out state are never reported."""
    await _recorded_kitchen_light(hass)

    assert (
        await _states_found(
            hass,
            issue_registry,
            {"type": "button", "entity": "light.kitchen", "visibility": [condition]},
        )
        is None
    )


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize("value", ["1.0", " 12 ", "0x1f", "-Infinity", 3])
async def test_state_filter_numbers_are_fine(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, value: Any
) -> None:
    """Test a state filter that might be compared as a number is not read."""
    await _recorded_kitchen_light(hass)

    assert (
        await _states_found(
            hass,
            issue_registry,
            _entity_filter({"entity": "light.kitchen", "state_filter": [value]}),
        )
        is None
    )


async def test_dashboard_saved_meanwhile_is_left_for_the_next_round(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test nothing is reported for a dashboard that changed while looking.

    The entities are asked about in between reading and reporting, and the
    recorder can take its time. Saving a dashboard starts the next round.
    """
    _kitchen_light(hass)
    configs = [
        {"views": [{"cards": [_visible_when(condition="state", state="On")]}]},
        {"views": [{"cards": [_visible_when(condition="state", state="on")]}]},
    ]

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the next version every time it is read."""
        del force
        return configs.pop(0) if len(configs) > 1 else configs[0]

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": SimpleNamespace(
            url_path="lovelace", config={"title": "Overview"}, async_load=async_load
        )
    }
    await repair.async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


async def test_fixed_is_cleared(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the issue goes once the entity turns out to be in that state."""
    _kitchen_light(hass)

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": dashboard(_visible_when(condition="state", state="On"))
    }
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, ISSUE)

    hass.states.async_set("light.kitchen", "On")
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, ISSUE) is None


async def test_not_before_the_recorder_settles(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test nothing is looked at until a while after starting."""
    _kitchen_light(hass)

    await async_assert_waits_for_the_recorder(
        hass,
        issue_registry,
        SpookRepair,
        ISSUE,
        _visible_when(condition="state", state="On"),
    )


async def test_draft_card_is_checked_for_states(hass: HomeAssistant) -> None:
    """Test a draft dashboard card gets the same answer as the repair."""
    _kitchen_light(hass)

    found = await async_check_draft(
        hass, "dashboard", _visible_when(condition="state", state="On")
    )

    assert found == {"states": ["light.kitchen:On (did you mean on?)"]}


@pytest.mark.usefixtures("recorder_mock")
async def test_a_number_shaped_like_an_entity_id_is_still_a_state(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test `"1.0"` is judged: the frontend reads it as a number, not an entity.

    It has the shape of an entity ID, but the frontend only looks a value up
    as an entity when it is no number.
    """
    await _recorded_kitchen_light(hass)

    found = await _states_found(
        hass,
        issue_registry,
        _visible_when(condition="state", entity="light.kitchen", state="1.0"),
    )

    assert found == "- `1.0` for `light.kitchen`"
