"""Tests for states named in a guard, or in a list, in automations.

A state held to not be one the entity is never in always holds: that is how
a guard is written. A list matches as long as one state in it can happen.
Neither is a mistake, unless a state in it differs from a real one in case
alone, or nothing in the list can ever be.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant.components.recorder.common import (
    async_wait_recording_done,
)

from homeassistant.components.light import LightEntity
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.automation.repairs.unknown_state_references import (
    SpookRepair,
)
from tests.entity_objects import give_entity_objects
from tests.repair_helpers import async_issue_about, async_setup_template_automation

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "automation_unknown_state_references_automation.haunted"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_db_url: str,
    enable_custom_integrations: None,
) -> None:
    """Prepare the recorder's database before Home Assistant starts.

    The recorder fixtures insist on going first, and the shared fixture that
    enables custom integrations starts Home Assistant.
    """
    _ = recorder_db_url, enable_custom_integrations


async def _async_kitchen_light_with_history(hass: HomeAssistant) -> None:
    """Set up the kitchen light, with a whole history of being on and off.

    With the whole history, a light is reported for anything else it is
    asked to be, not only for a slip in case.
    """
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("light.kitchen", "off")
    await async_wait_recording_done(hass)


async def _async_automation(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Set up the haunted automation, waiting on an event, with this on top."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "triggers": [{"trigger": "event", "event_type": "boo"}],
                    "actions": [],
                    **config,
                }
            ]
        },
    )
    await hass.async_block_till_done()


async def _async_states_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> str | None:
    """Look once, and return the states the issue lists, if there is one."""
    await SpookRepair(hass).async_inspect()

    if (issue := async_issue_about(issue_registry, ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["states"]


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "template",
    [
        pytest.param(
            "{{ states('light.kitchen') not in ['unavailable', 'unknown', 'none', ''] }}",
            id="not in the four that mean nothing",
        ),
        pytest.param("{{ states('light.kitchen') != 'None' }}", id="not None"),
        pytest.param(
            "{{ states('light.kitchen') != 'unavailable' }}", id="not unavailable"
        ),
        pytest.param(
            "{{ states('light.kitchen') in ['on', 'home', 'open'] }}",
            id="in a list that has on",
        ),
        pytest.param(
            "{{ is_state('light.kitchen', ['on', 'playing']) }}",
            id="is_state with a list that has on",
        ),
        pytest.param(
            "{{ not is_state('light.kitchen', 'none') }}", id="not is_state none"
        ),
        pytest.param(
            "{{ not (states('light.kitchen') == 'none') }}",
            id="not around a comparison",
        ),
        pytest.param(
            "{{ 'light.kitchen' is not is_state(['none', '']) }}",
            id="is not is_state with a list",
        ),
    ],
)
async def test_guards_and_lists_in_templates_are_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    template: str,
) -> None:
    """Test a guard, or a list with a state that can happen, is no mistake."""
    await _async_kitchen_light_with_history(hass)
    await async_setup_template_automation(hass, template)

    assert await _async_states_reported(hass, issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "config",
    [
        pytest.param(
            {
                "conditions": [
                    {
                        "condition": "state",
                        "entity_id": "light.kitchen",
                        "state": ["on", "home"],
                    }
                ]
            },
            id="condition with a list that has on",
        ),
        pytest.param(
            {
                "triggers": [
                    {
                        "trigger": "state",
                        "entity_id": "light.kitchen",
                        "to": ["on", "home"],
                    }
                ]
            },
            id="trigger to a list that has on",
        ),
        pytest.param(
            {
                "triggers": [
                    {
                        "trigger": "state",
                        "entity_id": "light.kitchen",
                        "not_to": "none",
                    }
                ]
            },
            id="trigger not to none",
        ),
        pytest.param(
            {
                "triggers": [
                    {
                        "trigger": "state",
                        "entity_id": "light.kitchen",
                        "to": "on",
                        "not_from": ["unavailable", "unknown", "none"],
                    }
                ]
            },
            id="trigger not from what means nothing",
        ),
    ],
)
async def test_guards_and_lists_in_triggers_and_conditions_are_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
) -> None:
    """Test state triggers and conditions are judged the way templates are."""
    await _async_kitchen_light_with_history(hass)
    await _async_automation(hass, config)

    assert await _async_states_reported(hass, issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "config",
    [
        pytest.param(
            {
                "conditions": [
                    {
                        "condition": "template",
                        "value_template": (
                            "{{ states('light.kitchen') in ['home', 'open'] }}"
                        ),
                    }
                ]
            },
            id="template",
        ),
        pytest.param(
            {
                "triggers": [
                    {
                        "trigger": "state",
                        "entity_id": "light.kitchen",
                        "to": ["home", "open"],
                    }
                ]
            },
            id="trigger",
        ),
    ],
)
async def test_a_list_that_can_never_match_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
) -> None:
    """Test a list without a single state the entity can be in is reported."""
    await _async_kitchen_light_with_history(hass)
    await _async_automation(hass, config)

    assert await _async_states_reported(hass, issue_registry) == (
        "- `home` for `light.kitchen`\n- `open` for `light.kitchen`"
    )


@pytest.mark.parametrize(
    "template",
    [
        pytest.param("{{ states('light.kitchen') != 'On' }}", id="not"),
        pytest.param(
            "{{ states('light.kitchen') not in ['unavailable', 'On'] }}",
            id="not in a list",
        ),
        pytest.param(
            "{{ states('light.kitchen') in ['on', 'On', 'home'] }}",
            id="in a list that has on",
        ),
        pytest.param("{{ states('light.kitchen') == 'On' }}", id="on its own"),
    ],
)
async def test_a_slip_in_case_is_always_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    template: str,
) -> None:
    """Test a state that differs from a real one in case alone is reported.

    A guard against `On` never holds back a light that is `on`, and a list
    with `On` in it never matches it. Without a recorder, so the slip in
    case is all there is to report.
    """
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "off")
    await async_setup_template_automation(hass, template)

    assert await _async_states_reported(hass, issue_registry) == (
        "- `On` for `light.kitchen` (did you mean `on`?)"
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_a_state_on_its_own_is_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a state held to be just that one, never there, is reported."""
    await _async_kitchen_light_with_history(hass)
    await async_setup_template_automation(
        hass, "{{ is_state('light.kitchen', 'none') }}"
    )

    assert await _async_states_reported(hass, issue_registry) == (
        "- `none` for `light.kitchen`"
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_a_guard_does_not_hide_the_same_state_elsewhere(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test how a state is compared counts per automation, not per state.

    One automation guards against `none`, another waits for the light to be
    `none`. All automations are judged in one go, and only the second one is
    wrong.
    """
    await _async_kitchen_light_with_history(hass)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "guarded",
                    "alias": "Guarded",
                    "triggers": [{"trigger": "event", "event_type": "boo"}],
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ states('light.kitchen') not in ['none'] }}"
                            ),
                        }
                    ],
                    "actions": [],
                },
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "triggers": [
                        {
                            "trigger": "state",
                            "entity_id": "light.kitchen",
                            "to": "none",
                        }
                    ],
                    "actions": [],
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert await _async_states_reported(hass, issue_registry) == (
        "- `none` for `light.kitchen`"
    )
    assert (
        async_issue_about(
            issue_registry, "automation_unknown_state_references_automation.guarded"
        )
        is None
    )
