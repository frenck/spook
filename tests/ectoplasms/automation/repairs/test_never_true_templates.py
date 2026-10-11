"""Tests for the automation templates that can never pass repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import yaml

from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook import draft_checking
from custom_components.spook.ectoplasms.automation.repairs.never_true_templates import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "automation_never_true_templates_automation.haunted"

EVENT = {"trigger": "event", "event_type": "haunt"}

# Long enough for a running script to get to its next step.
SETTLE = 0.05

# Fine as a condition, a trigger and a wait: renders `True` or `False`.
FINE = "{{ is_state('light.hall', 'on') }}"

# The quotes are text, so this renders `"True"` or `"False"`, quotes and all.
QUOTED = "\"{{ is_state('light.hall', 'on') }}\""

# No Jinja at all, so this is exactly what it renders.
WITHOUT_DELIMITERS = "is_state('light.hall', 'on')"

# Renders `on` or `off`: a trigger takes `on`, a condition only takes `true`.
ON_OR_OFF = "{{ 'on' if is_state('light.hall', 'on') else 'off' }}"

# A YAML comment inside Jinja is printed: `True # hall` or `False # hall`.
COMMENTED = "{{ is_state('light.hall', 'on') }} # the hall light"

# Renders `on` or `yes`: both read as true, so it never changes from false to
# true. It is rendered again whenever the sensor changes.
ALWAYS_TRUTHY = "{{ 'on' if states('sensor.load') | float > 1 else 'yes' }}"


def _template_condition(template: Any) -> dict[str, Any]:
    """Return a template condition."""
    return {"condition": "template", "value_template": template}


def _template_trigger(template: Any) -> dict[str, Any]:
    """Return a template trigger."""
    return {"trigger": "template", "value_template": template}


async def _found(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    *,
    triggers: list[Any] | None = None,
    conditions: list[Any] | None = None,
    actions: list[Any] | None = None,
) -> set[str] | None:
    """Set up the haunted automation, inspect it, and return what is reported.

    `None` when there is no issue at all, so a test tells "nothing found"
    apart from an issue that found nothing.
    """
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "triggers": triggers or [EVENT],
                    "conditions": conditions or [],
                    "actions": actions or [],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("automation.haunted").state == "on"

    await SpookRepair(hass).async_inspect()

    if (issue := async_issue_about(issue_registry, ISSUE)) is None:
        return None
    return {
        line.removeprefix("- `").removesuffix("`")
        for line in issue.translation_placeholders["templates"].splitlines()
    }


async def test_a_quoted_condition_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a condition with quotes around its template is reported."""
    assert await _found(
        hass, issue_registry, conditions=[_template_condition(QUOTED)]
    ) == {QUOTED}

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "automation_never_true_templates"
    assert issue.translation_placeholders == {
        "automation": "Haunted",
        "edit": "/config/automation/edit/haunted",
        "entity_id": "automation.haunted",
        "templates": f"- `{QUOTED}`",
    }
    assert issue.learn_more_url == (
        "https://spook.boo/automation#templates-that-can-never-pass"
    )


@pytest.mark.parametrize(
    "template",
    [
        WITHOUT_DELIMITERS,
        # The opening delimiters are missing, the closing ones are just text.
        "is_state('light.hall', 'on') }}",
        "yes",
        "on",
        "1",
    ],
)
async def test_a_condition_without_jinja_that_is_not_true_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test a condition without Jinja is reported, unless it says `true`.

    A condition takes only `true`, so `on`, `yes` and `1` do not pass either.
    """
    assert await _found(
        hass, issue_registry, conditions=[_template_condition(template)]
    ) == {template}


@pytest.mark.parametrize("template", ["true", "True", " TRUE ", True])
async def test_a_condition_that_says_true_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: Any
) -> None:
    """Test a condition without Jinja that is `true`, in any case, passes.

    `value_template: true` in YAML is a boolean, which Home Assistant takes as
    the template `True`.
    """
    assert (
        await _found(hass, issue_registry, conditions=[_template_condition(template)])
        is None
    )


@pytest.mark.parametrize(
    "template",
    [
        FINE,
        "{% if is_state('light.hall', 'on') %}true{% else %}false{% endif %}",
        "{{ 'true' if is_state('light.hall', 'on') else 'false' }}",
        # Whitespace and Jinja's own comments print nothing that matters.
        "{# the hall light #}\n  {{ is_state('light.hall', 'on') }}\n",
        "{%- set hall = is_state('light.hall', 'on') -%}\n{{ hall }}",
        # A test written as a constant that picks the branch printing `true`.
        "{{ 'true' if true else 'off' }}",
        "{% if false %}off{% elif true %}true{% else %}off{% endif %}",
    ],
)
async def test_conditions_that_can_pass_are_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test conditions that can render `true` are not reported."""
    assert (
        await _found(hass, issue_registry, conditions=[_template_condition(template)])
        is None
    )


@pytest.mark.parametrize(
    "template",
    [
        # A state can be any text, `true` too.
        "{{ states('input_text.answer') }}",
        "{{ trigger.to_state.state }}",
        # Whatever a variable or a call prints is only known while running.
        "{{ answer }}",
        "{% for light in lights %}{{ light }}{% endfor %}",
    ],
)
async def test_conditions_that_depend_on_a_run_are_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test conditions whose output is only known while running are never judged."""
    assert (
        await _found(hass, issue_registry, conditions=[_template_condition(template)])
        is None
    )


@pytest.mark.parametrize(
    "template",
    [
        "{% if is_state('light.hall', 'on') %}on and {% endif %}{{ true }}",
        (
            "{% if is_state('light.hall', 'on') %}on and {% endif %}"
            "{{ is_state('light.den', 'on') }}"
        ),
    ],
)
async def test_text_in_a_branch_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test text printed only in some branch is not taken as always there.

    When the hall light is off, these print only `True`, or whatever the den
    light says, which can pass.
    """
    assert (
        await _found(hass, issue_registry, conditions=[_template_condition(template)])
        is None
    )


@pytest.mark.parametrize(
    "template",
    [
        COMMENTED,
        ON_OR_OFF,
        "{% if is_state('light.hall', 'on') %}on{% else %}off{% endif %}",
        "{{ is_state('light.hall', 'on') }} and {{ is_state('light.den', 'on') }}",
        # A branch behind a test written as a constant that never runs.
        "{{ 'true' if false else 'off' }}",
        "{{ 'off' if true else 'true' }}",
        (
            "{% if false %}true{% elif is_state('light.hall', 'on') %}on"
            "{% elif true %}off{% else %}true{% endif %}"
        ),
    ],
)
async def test_a_condition_that_never_renders_true_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test a condition whose every possible output is something besides `true`."""
    assert await _found(
        hass, issue_registry, conditions=[_template_condition(template)]
    ) == {template}


@pytest.mark.parametrize(
    "template",
    [
        # `on` reads as true for a trigger.
        ON_OR_OFF,
        # Python skips the comment, and so does the trigger.
        COMMENTED,
        FINE,
        # A sign can start a number, like `-1`.
        "- {{ is_state('light.hall', 'on') }}",
        # Python skips a comment in front, and brackets around `True`.
        "# the hall light\n{{ is_state('light.hall', 'on') }}",
        "({{ is_state('light.hall', 'on') }})",
        # The quote is only there sometimes. Without it, this can be `True`.
        (
            "{% if is_state('light.hall', 'on') %}\"{% endif %}"
            "{{ is_state('light.den', 'on') }}"
        ),
    ],
)
async def test_triggers_that_can_fire_are_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test a trigger is held to what a trigger takes, not to what a condition takes."""
    assert (
        await _found(hass, issue_registry, triggers=[_template_trigger(template)])
        is None
    )


@pytest.mark.parametrize(
    "template",
    [
        QUOTED,
        "'{{ is_state('light.hall', 'on') }}'",
        WITHOUT_DELIMITERS,
        "off",
        # Text that nothing true starts with.
        "value_template: {{ is_state('light.hall', 'on') }}",
    ],
)
async def test_a_trigger_that_never_fires_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test a trigger that can never render what reads as true is reported."""
    assert await _found(
        hass, issue_registry, triggers=[_template_trigger(template)]
    ) == {template}


@pytest.mark.parametrize(
    "template",
    [
        ALWAYS_TRUTHY,
        "{{ 'true' }}",
        "{% if is_state('light.hall', 'on') %}on{% else %}1{% endif %}",
    ],
)
async def test_a_trigger_that_always_reads_as_true_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test a trigger that never reads as false is reported.

    It only fires after a render that does not read as true, so it never does.
    """
    assert await _found(
        hass, issue_registry, triggers=[_template_trigger(template)]
    ) == {template}


async def test_home_assistant_never_fires_a_trigger_that_always_reads_as_true(
    hass: HomeAssistant,
) -> None:
    """Test what the trigger check relies on, against Home Assistant itself.

    Not its first render, and not a render error in between, arms it.
    """
    hass.states.async_set("sensor.load", "unavailable")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "triggers": [_template_trigger(ALWAYS_TRUTHY)],
                "actions": [{"event": "fired"}],
            }
        },
    )
    fired = []
    hass.bus.async_listen("fired", fired.append)

    for state in ("0", "unavailable", "5", "0", "unavailable", "5"):
        hass.states.async_set("sensor.load", state)
        await hass.async_block_till_done()

    assert not fired


async def test_home_assistant_ends_a_wait_reading_as_true_once_rendered_again(
    hass: HomeAssistant,
) -> None:
    """Test why a wait that reads as true but is rendered again is left alone.

    It went from `yes` to `yes`, never from false to true, yet it ends: the
    watch takes its first render as a change.
    """
    hass.states.async_set("sensor.load", "0")
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "haunted": {
                    "sequence": [
                        {"wait_template": ALWAYS_TRUTHY, "timeout": 60},
                        {
                            "event": "fired",
                            "event_data": {"completed": "{{ wait.completed }}"},
                        },
                    ]
                }
            }
        },
    )
    fired = []
    hass.bus.async_listen("fired", fired.append)

    running = hass.async_create_task(
        hass.services.async_call("script", "haunted", blocking=True)
    )
    await asyncio.sleep(SETTLE)
    hass.states.async_set("sensor.load", "0.5")
    await asyncio.sleep(SETTLE)

    # Well before its own timeout of a minute.
    async with asyncio.timeout(5):
        await running

    assert [event.data["completed"] for event in fired] == [True]


@pytest.mark.parametrize("template", ["on", "{{ 'on' }}"])
async def test_home_assistant_never_ends_a_wait_that_is_never_rendered_again(
    hass: HomeAssistant, template: str
) -> None:
    """Test why a wait that reads as true but is never rendered again is reported.

    The watch renders it once to start with, and that render never counts.
    With nothing in it to track, there is no other render, so it times out.
    """
    hass.states.async_set("sensor.load", "0")
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "haunted": {
                    "sequence": [
                        {"wait_template": template, "timeout": 0.5},
                        {
                            "event": "fired",
                            "event_data": {"completed": "{{ wait.completed }}"},
                        },
                    ]
                }
            }
        },
    )
    fired = []
    hass.bus.async_listen("fired", fired.append)

    running = hass.async_create_task(
        hass.services.async_call("script", "haunted", blocking=True)
    )
    await asyncio.sleep(SETTLE)
    hass.states.async_set("sensor.load", "0.5")

    async with asyncio.timeout(5):
        await running
    await hass.async_block_till_done()

    assert [event.data["completed"] for event in fired] == [False]


@pytest.mark.parametrize("template", ["on", "true", "1"])
async def test_a_trigger_without_jinja_that_reads_as_true_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test a trigger without Jinja that reads as true is not reported.

    It never changes, so it never fires either. That is a different ghost,
    and not one this repair says anything about.
    """
    assert (
        await _found(hass, issue_registry, triggers=[_template_trigger(template)])
        is None
    )


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        # Without Jinja, a wait is only checked like a condition, once.
        ("on", {"on"}),
        (QUOTED, {QUOTED}),
        # Jinja that always prints the same text never changes either.
        ("{{ 'on' }}", {"{{ 'on' }}"}),
        ("{{ 'true' }}", None),
        # Jinja that only ever prints what reads as true never goes from
        # false to true, so its watch never fires.
        (
            "{% if true %}on{% else %}yes{% endif %}",
            {"{% if true %}on{% else %}yes{% endif %}"},
        ),
        # Unless it is rendered again: the first render the watch sees ends
        # the wait when it reads as true.
        (ALWAYS_TRUTHY, None),
        ("{{ 'true' if is_state('light.hall', 'on') else 'yes' }}", None),
        # With Jinja, a wait takes `on` once its template changes.
        (ON_OR_OFF, None),
        ("true", None),
        (FINE, None),
    ],
)
async def test_waits_are_read_like_home_assistant_waits(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    template: str,
    expected: set[str] | None,
) -> None:
    """Test a wait is held to what it takes, with and without Jinja."""
    assert (
        await _found(
            hass,
            issue_registry,
            actions=[{"wait_template": template, "timeout": 1}],
        )
        == expected
    )


async def test_templates_are_found_wherever_they_nest(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test every place a template has to pass is read."""

    def numbered(number: int) -> str:
        return f"is_state('light.hall', 'on') and {number}"

    assert await _found(
        hass,
        issue_registry,
        triggers=[EVENT, {"triggers": [_template_trigger(numbered(1))]}],
        conditions=[
            _template_condition(numbered(2)),
            f"{{{{ 'two' }}}} {numbered(3)}",
            {"or": [_template_condition(numbered(4))]},
            {"condition": "not", "conditions": [_template_condition(numbered(5))]},
        ],
        actions=[
            {"condition": f"{{{{ 'step' }}}} {numbered(6)}"},
            {"if": [_template_condition(numbered(7))], "then": []},
            {
                "choose": [
                    {
                        "conditions": [_template_condition(numbered(8))],
                        "sequence": [{"wait_template": numbered(9)}],
                    }
                ],
                "default": [
                    {
                        "repeat": {
                            "while": [_template_condition(numbered(10))],
                            "sequence": [
                                {
                                    "repeat": {
                                        "until": [_template_condition(numbered(11))],
                                        "sequence": [],
                                    }
                                }
                            ],
                        }
                    }
                ],
            },
            {
                "parallel": [
                    {"sequence": [{"wait_template": numbered(12)}]},
                    {"wait_for_trigger": [_template_trigger(numbered(13))]},
                ]
            },
            {
                "sequence": [
                    {
                        "condition": "and",
                        "conditions": [f"{{{{ 'and' }}}} {numbered(14)}"],
                    }
                ]
            },
        ],
    ) == {
        numbered(1),
        numbered(2),
        f"{{{{ 'two' }}}} {numbered(3)}",
        numbered(4),
        numbered(5),
        f"{{{{ 'step' }}}} {numbered(6)}",
        numbered(7),
        numbered(8),
        numbered(9),
        numbered(10),
        numbered(11),
        numbered(12),
        numbered(13),
        f"{{{{ 'and' }}}} {numbered(14)}",
    }


async def test_disabled_parts_are_left_out(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test templates in disabled triggers, conditions and steps are not read."""
    assert (
        await _found(
            hass,
            issue_registry,
            triggers=[EVENT, {**_template_trigger(QUOTED), "enabled": False}],
            conditions=[{**_template_condition(QUOTED), "enabled": False}],
            actions=[
                {"wait_template": "on", "enabled": False},
                {
                    "if": [{**_template_condition(QUOTED), "enabled": False}],
                    "then": [],
                },
            ],
        )
        is None
    )


async def test_payloads_and_other_templates_are_left_out(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test only templates that have to pass are read.

    Service data that looks like a condition is somebody's data, and a
    message or a numeric state `value_template` is not held to `true`.
    """
    assert (
        await _found(
            hass,
            issue_registry,
            triggers=[
                {
                    "trigger": "numeric_state",
                    "entity_id": "sensor.power",
                    "value_template": "{{ state.state | float * 1000 }} W",
                    "above": 10,
                },
            ],
            actions=[
                {
                    "action": "persistent_notification.create",
                    "data": {
                        "message": QUOTED,
                        "condition": "template",
                        "value_template": QUOTED,
                    },
                },
                {"variables": {"wait_template": "on"}},
                {"repeat": {"for_each": [{"wait_template": "on"}], "sequence": []}},
            ],
        )
        is None
    )


async def test_a_long_template_is_shown_on_one_line(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a template over several lines is listed on one."""
    assert await _found(
        hass,
        issue_registry,
        conditions=[
            _template_condition(
                "\"{{ is_state('light.hall', 'on')\n   and is_state('light.den', 'on') }}\"\n"
            )
        ],
    ) == {"\"{{ is_state('light.hall', 'on') and is_state('light.den', 'on') }}\""}


# From forum threads, as the person posted them, only the conditions and
# triggers. Read as YAML, so block scalars fold the way they did for them.
FORUM_CONDITIONS = {
    # Quotes inside a `>-` block.
    "https://community.home-assistant.io/t/738044": """
- condition: template
  value_template: >-
    "{{ states('sensor.solar_pv_output_over_last_5_minutes') | float(0) >
    states('input_number.solar_peak_5_minute_output_today') | float(0) }}"
""",
    # No delimiters at all.
    "https://community.home-assistant.io/t/944497": """
- condition: template
  value_template: trigger.from_state.state != "unknown"
""",
    # Brackets, but no delimiters.
    "https://community.home-assistant.io/t/887583": """
- condition: template
  value_template: ((states("sensor.mysa_X_current_temperature")>(state_attr('climate.mysa_X_thermostat','temperature') +0.7)))
""",
    # The opening `{{` is missing.
    "https://community.home-assistant.io/t/925854": """
- condition: template
  value_template: >-
    state_attr('sensor.sm_s921u_last_notification' , 'package') ==
    'com.transfinder.stopfinder' }}
""",
    # YAML pasted into the template field of the editor.
    "https://community.home-assistant.io/t/886273": """
- condition: template
  value_template: |
    - condition: template
      value_template: >
        {% set last_off = states('input_datetime.last_manual_light_off') %}
        {% if last_off == 'unknown' %}
          true
        {% else %}
          {{ (now() - as_local(as_datetime(last_off))).total_seconds() > 14400 }}
        {% endif %}
""",
}


@pytest.mark.parametrize("thread", FORUM_CONDITIONS)
async def test_forum_conditions_are_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, thread: str
) -> None:
    """Test conditions people wrote on the forums are caught."""
    conditions = yaml.safe_load(FORUM_CONDITIONS[thread])
    template = conditions[0]["value_template"]

    assert await _found(hass, issue_registry, conditions=conditions) == {
        " ".join(template.split())
    }


async def test_a_forum_trigger_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a quoted template trigger, https://community.home-assistant.io/t/959641."""
    triggers = yaml.safe_load(
        """
- trigger: template
  value_template: >-
    "{{ is_state('input_boolean.pv_ds_home', 'off') and
    is_state('input_boolean.pv_sc_home', 'off') }}"
"""
    )

    assert await _found(hass, issue_registry, triggers=triggers) == {
        (
            "\"{{ is_state('input_boolean.pv_ds_home', 'off') and "
            "is_state('input_boolean.pv_sc_home', 'off') }}\""
        )
    }


async def test_a_forum_condition_reading_a_state_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a condition printing a state is not judged, however likely `on` is.

    https://community.home-assistant.io/t/778736: a binary sensor's state is
    `on`, never `true`, so this never passed. Which state it prints is only
    known while running, and that is not read here.
    """
    conditions = yaml.safe_load(
        """
- condition: template
  value_template: >-
    {{ states('binary_sensor.octopus_energy_target_agile_' ~
    '{:02d}'.format(states('input_number.sensor_selector') | int)) }}
"""
    )

    assert await _found(hass, issue_registry, conditions=conditions) is None


async def test_a_reload_with_the_template_fixed_clears_the_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the issue goes once the fixed automation is reloaded."""
    assert await _found(
        hass, issue_registry, conditions=[_template_condition(QUOTED)]
    ) == {QUOTED}

    repair = SpookRepair(hass)
    await repair.async_activate()

    fixed = {
        "automation": [
            {
                "id": "haunted",
                "alias": "Haunted",
                "triggers": [EVENT],
                "conditions": [_template_condition(FINE)],
                "actions": [],
            }
        ]
    }
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=fixed,
    ):
        await hass.services.async_call("automation", "reload", blocking=True)
    await hass.async_block_till_done()

    # The look after a reload is debounced.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()

    assert async_issue_about(issue_registry, ISSUE) is None
    await repair.async_deactivate()


async def test_an_automation_that_failed_to_load_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a broken automation is not reported: Home Assistant says so itself."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "triggers": [{"trigger": "no_such_platform"}],
                    "conditions": [_template_condition(QUOTED)],
                    "actions": [],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("automation.haunted").state == "unavailable"

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


async def test_an_automation_without_an_id_links_to_the_list(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an automation from YAML without an ID has no editor to link to."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "Haunted",
                    "triggers": [EVENT],
                    "conditions": [_template_condition(QUOTED)],
                    "actions": [],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_placeholders["edit"] == "/config/automation/dashboard"


BLUEPRINT = """
blueprint:
  name: Hall light
  domain: automation
  input:
    when:
      selector:
        template:
triggers:
  - trigger: event
    event_type: haunt
conditions:
  - condition: template
    value_template: !input when
actions: []
"""


@pytest.mark.parametrize(
    ("when", "expected"),
    [(FINE, None), (QUOTED, {QUOTED})],
)
async def test_an_automation_on_a_blueprint_is_read_with_its_inputs(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    tmp_path: Path,
    when: str,
    expected: set[str] | None,
) -> None:
    """Test a blueprint's templates are the ones its inputs fill in."""
    hass.config.config_dir = str(tmp_path)
    blueprint = tmp_path / "blueprints" / "automation" / "frenck" / "hall.yaml"
    blueprint.parent.mkdir(parents=True)
    blueprint.write_text(BLUEPRINT, encoding="utf-8")

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "use_blueprint": {
                        "path": "frenck/hall.yaml",
                        "input": {"when": when},
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("automation.haunted").state == "on"

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    found = None if issue is None else issue.translation_placeholders["templates"]
    assert found == (None if expected is None else f"- `{QUOTED}`")


async def test_a_draft_is_checked_for_templates_that_never_pass(
    hass: HomeAssistant,
) -> None:
    """Test a draft automation is asked about its templates like a saved one."""
    hass.states.async_set("light.hall", "on")
    assert await draft_checking.async_check_draft(
        hass,
        "automation",
        {
            "triggers": [EVENT],
            "conditions": [_template_condition(QUOTED), _template_condition(FINE)],
            "actions": [],
        },
    ) == {"templates": [QUOTED]}
