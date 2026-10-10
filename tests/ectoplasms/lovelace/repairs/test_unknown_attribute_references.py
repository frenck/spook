"""Tests for the Lovelace unknown attribute references repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)


from custom_components.spook.draft_checking import async_check_draft
from custom_components.spook.ectoplasms.lovelace.repairs.unknown_attribute_references import (
    SpookRepair,
)
from tests.ectoplasms.lovelace.repairs.dashboard_helpers import (
    async_assert_waits_for_the_recorder,
    dashboard,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "lovelace_unknown_attribute_references_lovelace"
FOUND = "- `Brightness` of `light.kitchen` (did you mean `brightness`?)"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_db_url: str,
    enable_custom_integrations: None,
) -> None:
    """Prepare the recorder's database before Home Assistant starts."""
    _ = recorder_db_url, enable_custom_integrations


async def _attributes_found(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, *cards: Any
) -> str | None:
    """Inspect a dashboard with these cards, and return the attributes reported."""
    repair = SpookRepair(hass)
    repair._dashboards = {"lovelace": dashboard(*cards)}  # noqa: SLF001
    await repair.async_inspect()

    if (issue := async_issue_about(issue_registry, ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["attributes"]


def _kitchen_light(hass: HomeAssistant) -> None:
    """Make a light that is on, at full brightness."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})


async def test_visibility_condition_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a visibility condition on an attribute never had is reported."""
    _kitchen_light(hass)

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": dashboard(
            {
                "type": "button",
                "visibility": [
                    {
                        "condition": "numeric_state",
                        "entity": "light.kitchen",
                        "attribute": "Brightness",
                        "above": 100,
                    }
                ],
            }
        )
    }
    await repair.async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "lovelace_unknown_attribute_references"
    assert issue.translation_placeholders == {
        "attributes": FOUND,
        "dashboard": "Overview",
        "edit": "/lovelace/kitchen?edit=1",
    }


@pytest.mark.parametrize(
    "card",
    [
        # Conditions, in every shape, with the card's own entity when they
        # have none.
        {
            "type": "tile",
            "entity": "light.kitchen",
            "visibility": [
                {
                    "condition": "or",
                    "conditions": [
                        {"condition": "state", "attribute": "Brightness", "state": "1"}
                    ],
                }
            ],
        },
        {
            "type": "conditional",
            "conditions": [
                {"entity": "light.kitchen", "attribute": "Brightness", "state": "1"}
            ],
            "card": {"type": "markdown", "content": "Bright"},
        },
        # Fields showing an attribute of their own entity.
        {"type": "entity", "entity": "light.kitchen", "attribute": "Brightness"},
        {"type": "gauge", "entity": "light.kitchen", "attribute": "Brightness"},
        {
            "type": "entities",
            "entities": [
                {
                    "type": "attribute",
                    "entity": "light.kitchen",
                    "attribute": "Brightness",
                }
            ],
        },
        {
            "type": "picture-elements",
            "image": "/local/floorplan.png",
            "elements": [
                {
                    "type": "state-label",
                    "entity": "light.kitchen",
                    "attribute": "Brightness",
                }
            ],
        },
        {
            "type": "picture-glance",
            "image": "/local/kitchen.png",
            "entities": [{"entity": "light.kitchen", "attribute": "Brightness"}],
        },
        {
            "type": "map",
            "entities": [
                {
                    "entity": "light.kitchen",
                    "label_mode": "attribute",
                    "attribute": "Brightness",
                }
            ],
        },
        # What a tile or a badge shows.
        {
            "type": "tile",
            "entity": "light.kitchen",
            "state_content": ["state", "last_changed", "Brightness"],
        },
        {
            "type": "heading",
            "badges": [{"entity": "light.kitchen", "state_content": "Brightness"}],
        },
        # A filter on an attribute.
        {
            "type": "entity-filter",
            "entities": ["light.kitchen"],
            "state_filter": [
                {"operator": ">", "attribute": "Brightness", "value": 100}
            ],
        },
    ],
)
async def test_every_place_an_attribute_is_named_is_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, card: dict[str, Any]
) -> None:
    """Test each place the frontend reads an attribute is read."""
    _kitchen_light(hass)

    assert await _attributes_found(hass, issue_registry, card) == FOUND


@pytest.mark.parametrize(
    "card",
    [
        # Words, not attributes.
        {
            "type": "tile",
            "entity": "light.kitchen",
            "state_content": [
                "state",
                "name",
                "last-changed",
                "last_updated",
                "entity-id",
                "area_name",
            ],
        },
        # A map label that is not the attribute.
        {
            "type": "map",
            "entities": [
                {
                    "entity": "light.kitchen",
                    "label_mode": "name",
                    "attribute": "Brightness",
                }
            ],
        },
        # Not something the card does.
        {"type": "button", "entity": "light.kitchen", "attribute": "Brightness"},
        # Custom cards, and anything inside one.
        {
            "type": "custom:mushroom-entity-card",
            "entity": "light.kitchen",
            "attribute": "Brightness",
        },
        {
            "type": "custom:vertical-stack-in-card",
            "cards": [
                {"type": "entity", "entity": "light.kitchen", "attribute": "Brightness"}
            ],
        },
        # Templates and placeholders.
        {
            "type": "entity",
            "entity": "light.kitchen",
            "attribute": "{{ 'Brightness' }}",
        },
        {"type": "entity", "entity": "light.kitchen", "attribute": "[[[ return 1 ]]]"},
        {"type": "entity", "entity": "light.kitchen", "attribute": "${attr}"},
        # A condition without an entity on a card without one.
        {
            "type": "markdown",
            "content": "Bright",
            "visibility": [
                {"condition": "state", "attribute": "Brightness", "state": "1"}
            ],
        },
        # An entity that is not there.
        {"type": "entity", "entity": "light.gone", "attribute": "Brightness"},
    ],
)
async def test_what_is_not_an_attribute_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, card: dict[str, Any]
) -> None:
    """Test what the frontend does not read as an attribute is not judged."""
    _kitchen_light(hass)

    assert await _attributes_found(hass, issue_registry, card) is None


async def test_shared_filter_is_fine_when_one_entity_has_it(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a filter on an attribute one of its entities has is fine."""
    _kitchen_light(hass)
    hass.states.async_set("sensor.lamp", "1", {"Brightness": 3})

    assert (
        await _attributes_found(
            hass,
            issue_registry,
            {
                "type": "entity-filter",
                "entities": ["light.kitchen", "sensor.lamp"],
                "state_filter": [
                    {"operator": ">", "attribute": "Brightness", "value": 1}
                ],
            },
        )
        is None
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_never_had_is_reported_from_history(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an attribute the whole history never had is reported."""
    _kitchen_light(hass)
    await async_wait_recording_done(hass)

    found = await _attributes_found(
        hass,
        issue_registry,
        {"type": "entity", "entity": "light.kitchen", "attribute": "colour"},
    )

    assert found == "- `colour` of `light.kitchen`"


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_only_in_history_is_fine(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an attribute the entity once had is fine."""
    hass.states.async_set("light.kitchen", "on", {"colour": "red"})
    _kitchen_light(hass)
    await async_wait_recording_done(hass)

    assert (
        await _attributes_found(
            hass,
            issue_registry,
            {"type": "entity", "entity": "light.kitchen", "attribute": "colour"},
        )
        is None
    )


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "card",
    [
        # Words, not attributes.
        {
            "type": "tile",
            "entity": "light.kitchen",
            "state_content": [
                "state",
                "name",
                "last-changed",
                "last_updated",
                "entity-id",
                "area_name",
            ],
        },
        # Templates and placeholders.
        {"type": "entity", "entity": "light.kitchen", "attribute": "{{ 'x' }}"},
        {"type": "entity", "entity": "light.kitchen", "attribute": "[[[ return 1 ]]]"},
        {"type": "entity", "entity": "light.kitchen", "attribute": "${attr}"},
        # Not something the card does.
        {"type": "button", "entity": "light.kitchen", "attribute": "colour"},
        # Options a strategy keeps for the cards it makes.
        {
            "type": "grid",
            "strategy": {
                "type": "areas",
                "card": {"type": "entity", "entity": "light.kitchen", "attribute": "x"},
            },
        },
    ],
)
async def test_what_is_not_an_attribute_is_left_alone_with_history(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, card: dict[str, Any]
) -> None:
    """Test what is no attribute is not judged, even with the whole history."""
    _kitchen_light(hass)
    await async_wait_recording_done(hass)

    assert await _attributes_found(hass, issue_registry, card) is None


async def test_without_a_recorder_only_case_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an attribute nobody can rule out is not reported without history."""
    _kitchen_light(hass)

    assert (
        await _attributes_found(
            hass,
            issue_registry,
            {"type": "entity", "entity": "light.kitchen", "attribute": "colour"},
        )
        is None
    )


async def test_edit_link_points_at_the_view_with_the_finding(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the edit link opens the first view holding a finding."""
    _kitchen_light(hass)
    config = {
        "views": [
            {
                "cards": [
                    {
                        "type": "entity",
                        "entity": "light.kitchen",
                        "attribute": "brightness",
                    }
                ]
            },
            {
                "cards": [
                    {
                        "type": "entity",
                        "entity": "light.kitchen",
                        "attribute": "Brightness",
                    }
                ]
            },
        ]
    }

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the config."""
        del force
        return config

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "energy-ish": SimpleNamespace(
            url_path="energy-ish", config={"title": "Rooms"}, async_load=async_load
        )
    }
    await repair.async_inspect()

    issue = async_issue_about(
        issue_registry, "lovelace_unknown_attribute_references_energy-ish"
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["edit"] == "/energy-ish/1?edit=1"
    assert issue.translation_placeholders["dashboard"] == "Rooms"


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
        {"type": "entity", "entity": "light.kitchen", "attribute": "Brightness"},
    )


async def test_draft_card_is_checked_for_attributes(hass: HomeAssistant) -> None:
    """Test a draft dashboard card gets the same answer as the repair."""
    _kitchen_light(hass)

    found = await async_check_draft(
        hass,
        "dashboard",
        {"type": "entity", "entity": "light.kitchen", "attribute": "Brightness"},
    )

    assert found == {
        "attributes": ["light.kitchen:Brightness (did you mean brightness?)"]
    }
