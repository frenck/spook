"""Tests for the automation.run action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from re import escape
from typing import TYPE_CHECKING, Any

from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.core import Context, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import async_capture_events, mock_restore_cache
import pytest

from custom_components.spook.ectoplasms.automation.services.run import SpookService

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import Event, HomeAssistant

pytestmark = pytest.mark.usefixtures("spook_translations")

FRONT_DOOR = "automation.front_door"
RAN = "spook_ran"

# Every run says what it saw, so a test can tell which branch it took and
# what the `trigger` variable held.
REPORT = {
    "event": RAN,
    "event_data": {
        "branch": "{{ branch }}",
        "id": "{{ trigger.id }}",
        "idx": "{{ trigger.idx }}",
        "alias": "{{ trigger.alias }}",
        "platform": "{{ trigger.platform }}",
        # Rendered, "2" comes out as a number, so the type is asked apart.
        "as_text": "{{ trigger.id is string and trigger.idx is string }}",
        "to_state": "{{ trigger.to_state.state if trigger.to_state else '' }}",
        "reason": "{{ reason | default('') }}",
    },
}


def _automation(
    triggers: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    """Return the front door automation, with a choose on the trigger ID."""
    return {
        "id": "front_door",
        "alias": "Front door",
        "triggers": triggers,
        "actions": [
            {
                "choose": [
                    {
                        "conditions": [{"condition": "trigger", "id": "door_opened"}],
                        "sequence": [{"variables": {"branch": "opened"}}, REPORT],
                    },
                    {
                        "conditions": [{"condition": "trigger", "id": "door_closed"}],
                        "sequence": [{"variables": {"branch": "closed"}}, REPORT],
                    },
                ],
                "default": [{"variables": {"branch": "default"}}, REPORT],
            }
        ],
        **extra,
    }


OPENED = {
    "trigger": "state",
    "entity_id": "binary_sensor.door",
    "to": "on",
    "id": "door_opened",
    "alias": "Door opens",
}
CLOSED = {
    "trigger": "state",
    "entity_id": "binary_sensor.door",
    "to": "off",
    "id": "door_closed",
}
DOORBELL = {"trigger": "event", "event_type": "doorbell"}


async def _setup(
    hass: HomeAssistant,
    *automations: dict[str, Any],
    state: str = "on",
) -> list[Event]:
    """Set up the automations and the action, and catch what the runs report."""
    mock_restore_cache(
        hass,
        [State(f"automation.{automation['id']}", state) for automation in automations],
    )
    assert await async_setup_component(
        hass, "automation", {"automation": list(automations)}
    )
    await hass.async_block_till_done()

    SpookService(hass).async_register()
    return async_capture_events(hass, RAN)


async def _run(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    """Run the front door automation, and return what the action answered."""
    response = await hass.services.async_call(
        "automation",
        "run",
        {"entity_id": FRONT_DOOR, **data},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    assert response is not None
    return response


async def test_the_choose_takes_the_branch_of_the_trigger(hass: HomeAssistant) -> None:
    """The reason the action exists: `trigger.id` is there, and right."""
    ran = await _setup(hass, _automation([OPENED, CLOSED]))

    await _run(hass, trigger="door_closed")
    await _run(hass, trigger="door_opened")

    assert [event.data["branch"] for event in ran] == ["closed", "opened"]


async def test_the_trigger_variable_is_the_one_a_real_firing_hands_over(
    hass: HomeAssistant,
) -> None:
    """Compared with a real firing of the same trigger, not with a guess."""
    hass.states.async_set("binary_sensor.door", "off")
    ran = await _setup(hass, _automation([CLOSED, OPENED]))

    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    await _run(hass, trigger="door_opened")

    real, spooky = (
        {
            key: event.data[key]
            for key in ("id", "idx", "alias", "platform", "branch", "as_text")
        }
        for event in ran
    )
    assert (
        real
        == spooky
        == {
            "id": "door_opened",
            "idx": 1,
            "as_text": True,
            "alias": "Door opens",
            "platform": "state",
            "branch": "opened",
        }
    )


async def test_a_new_style_trigger_has_its_own_key_as_platform(
    hass: HomeAssistant,
) -> None:
    """Triggers like `switch.turned_on` put their whole key there, not a domain."""
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"x": {}}}
    )
    turned_on = {
        "trigger": "switch.turned_on",
        "target": {"entity_id": "input_boolean.x"},
        "options": {"behavior": "each"},
        "id": "turned_on",
    }
    ran = await _setup(hass, _automation([turned_on]))

    await hass.services.async_call(
        "input_boolean", "turn_on", {"entity_id": "input_boolean.x"}, blocking=True
    )
    await hass.async_block_till_done()
    await _run(hass)

    real, spooky = (
        {key: event.data[key] for key in ("id", "idx", "platform", "as_text")}
        for event in ran
    )
    assert (
        real
        == spooky
        == {
            "id": "turned_on",
            "idx": 0,
            "platform": "switch.turned_on",
            "as_text": True,
        }
    )


async def test_the_only_trigger_is_the_default(hass: HomeAssistant) -> None:
    """With one trigger there is nothing to choose."""
    ran = await _setup(hass, _automation([OPENED]))

    await _run(hass)

    assert ran[0].data["id"] == "door_opened"
    assert ran[0].data["branch"] == "opened"


async def test_the_only_enabled_trigger_is_the_default(hass: HomeAssistant) -> None:
    """A disabled one never fires, so it does not make the choice harder."""
    ran = await _setup(hass, _automation([{**OPENED, "enabled": False}, CLOSED]))

    await _run(hass)

    # Still counted where it stands, like Home Assistant does.
    assert ran[0].data["id"] == "door_closed"
    assert ran[0].data["idx"] == 1


async def test_several_triggers_and_none_named_is_refused(hass: HomeAssistant) -> None:
    """Spook does not guess which one was meant, and says what there is."""
    ran = await _setup(hass, _automation([OPENED, CLOSED, DOORBELL]))

    with pytest.raises(
        ServiceValidationError,
        match="more than one enabled trigger, so name the one to run it by: "
        "door_opened, door_closed, 2",
    ):
        await _run(hass)

    assert not ran


async def test_an_automation_without_triggers_is_refused(hass: HomeAssistant) -> None:
    """There is no trigger to stand in for, and Core's own action is the way."""
    ran = await _setup(hass, _automation([]))

    with pytest.raises(ServiceValidationError, match=escape("use automation.trigger")):
        await _run(hass)

    assert not ran


async def test_only_disabled_triggers_is_no_trigger_at_all(hass: HomeAssistant) -> None:
    """Naming one changes nothing: there is no list of others to offer."""
    ran = await _setup(hass, _automation([{**OPENED, "enabled": False}]))

    with pytest.raises(ServiceValidationError, match=escape("use automation.trigger")):
        await _run(hass, trigger="door_opened")

    assert not ran


async def test_an_unknown_trigger_is_refused(hass: HomeAssistant) -> None:
    """A typo is an error, with what it could have been."""
    ran = await _setup(hass, _automation([OPENED, CLOSED]))

    with pytest.raises(
        ServiceValidationError,
        match=escape(
            "automation.front_door has no trigger door_opend. "
            "Its enabled triggers are: door_opened, door_closed"
        ),
    ):
        await _run(hass, trigger="door_opend")

    assert not ran


async def test_a_position_is_a_trigger_id_counted_like_core(
    hass: HomeAssistant,
) -> None:
    """A nested `triggers:` list is flattened first, then counted.

    A disabled trigger keeps its place in the count. Pinned against real
    firings: the trigger Spook picks for a position is the very one that
    hands the run that `trigger.idx` when it fires itself.
    """

    def _event(name: str, **extra: Any) -> dict[str, Any]:
        return {"trigger": "event", "event_type": name, "alias": name, **extra}

    nested = _automation(
        [
            _event("first"),
            {"triggers": [_event("second"), _event("third")]},
            _event("fourth", enabled=False),
            _event("fifth"),
        ]
    )
    ran = await _setup(hass, nested)

    hass.bus.async_fire("third")
    hass.bus.async_fire("fifth")
    await hass.async_block_till_done()
    await _run(hass, trigger="2")
    await _run(hass, trigger=4)

    real_third, real_fifth, spooky_third, spooky_fifth = (
        {key: event.data[key] for key in ("id", "idx", "alias", "as_text")}
        for event in ran
    )
    assert (
        real_third
        == spooky_third
        == {
            "id": 2,
            "idx": 2,
            "alias": "third",
            "as_text": True,
        }
    )
    assert (
        real_fifth
        == spooky_fifth
        == {
            "id": 4,
            "idx": 4,
            "alias": "fifth",
            "as_text": True,
        }
    )


async def test_a_disabled_trigger_is_refused(hass: HomeAssistant) -> None:
    """A real one could never fire."""
    ran = await _setup(hass, _automation([{**OPENED, "enabled": False}, CLOSED]))

    with pytest.raises(
        ServiceValidationError,
        match=escape("Trigger door_opened of automation.front_door is disabled"),
    ):
        await _run(hass, trigger="door_opened")

    assert not ran


@pytest.mark.parametrize(
    ("enabled", "refused"),
    [
        ("{{ false }}", True),
        ("{{ true }}", False),
        ("{{ use_door }}", False),
        ("{{ undefined_thing.oops() }}", True),
    ],
)
async def test_a_templated_enabled_is_rendered_like_core_does(
    hass: HomeAssistant,
    enabled: str,
    refused: bool,  # noqa: FBT001
) -> None:
    """With the trigger variables, and one that does not render counts as off.

    Checked against Home Assistant itself: the trigger fires for real exactly
    when Spook runs by it.
    """
    ran = await _setup(
        hass,
        _automation(
            [{**OPENED, "enabled": enabled}, CLOSED],
            trigger_variables={"use_door": True},
        ),
    )

    hass.states.async_set("binary_sensor.door", "off")
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    fired_for_real = any(event.data["id"] == "door_opened" for event in ran)
    assert fired_for_real is not refused

    if refused:
        with pytest.raises(ServiceValidationError, match="is disabled"):
            await _run(hass, trigger="door_opened")
        return

    await _run(hass, trigger="door_opened")
    assert ran[-1].data["id"] == "door_opened"


async def test_the_conditions_are_checked(hass: HomeAssistant) -> None:
    """That is the difference with Core's own action, which skips them."""
    ran = await _setup(
        hass,
        _automation(
            [OPENED, CLOSED],
            conditions=[{"condition": "template", "value_template": "{{ allowed }}"}],
        ),
    )

    response = await _run(hass, trigger="door_opened", variables={"allowed": False})

    assert response == {FRONT_DOOR: {"ran": False}}
    assert not ran

    response = await _run(hass, trigger="door_opened", variables={"allowed": True})

    assert response == {FRONT_DOOR: {"ran": True}}
    assert len(ran) == 1


async def test_the_conditions_can_be_skipped(hass: HomeAssistant) -> None:
    """For a run that should happen whatever the conditions say."""
    ran = await _setup(
        hass,
        _automation(
            [OPENED],
            conditions=[{"condition": "template", "value_template": "{{ false }}"}],
        ),
    )

    response = await _run(hass, skip_condition=True)

    assert response == {FRONT_DOOR: {"ran": True}}
    assert len(ran) == 1


async def test_the_conditions_see_the_trigger(hass: HomeAssistant) -> None:
    """A `trigger` condition reads the same variable the actions do."""
    ran = await _setup(
        hass,
        _automation(
            [OPENED, CLOSED],
            conditions=[{"condition": "trigger", "id": "door_opened"}],
        ),
    )

    assert await _run(hass, trigger="door_closed") == {FRONT_DOOR: {"ran": False}}
    assert await _run(hass, trigger="door_opened") == {FRONT_DOOR: {"ran": True}}
    assert [event.data["id"] for event in ran] == ["door_opened"]


async def test_trigger_data_reaches_the_templates(hass: HomeAssistant) -> None:
    """Plain data, which a template reads like the State it stands in for."""
    ran = await _setup(hass, _automation([OPENED]))

    await _run(hass, trigger_data={"to_state": {"state": "on"}})

    assert ran[0].data["to_state"] == "on"
    assert ran[0].data["id"] == "door_opened"


@pytest.mark.parametrize("key", ["id", "idx", "alias", "platform"])
async def test_trigger_data_cannot_say_which_trigger_it_was(
    hass: HomeAssistant, key: str
) -> None:
    """Naming one trigger and passing off as another runs a branch nobody picked."""
    ran = await _setup(hass, _automation([OPENED, CLOSED]))

    with pytest.raises(
        ServiceValidationError, match=escape(f"Trigger data cannot set {key}")
    ):
        await _run(hass, trigger="door_closed", trigger_data={key: "door_opened"})

    assert not ran


async def test_an_error_in_the_actions_is_a_run_that_did_not_finish(
    hass: HomeAssistant,
) -> None:
    """Home Assistant logs it and hands nothing back; the call itself is fine."""
    automation = _automation([OPENED])
    automation["actions"] = [{"action": "nothing.at_all"}]
    await _setup(hass, automation)

    assert await _run(hass) == {FRONT_DOOR: {"ran": False}}


async def test_variables_reach_the_run(hass: HomeAssistant) -> None:
    """Like those of Core's own action."""
    ran = await _setup(hass, _automation([OPENED]))

    await _run(hass, variables={"reason": "testing"})

    assert ran[0].data["reason"] == "testing"


async def test_variables_cannot_replace_the_trigger(hass: HomeAssistant) -> None:
    """The trigger is what `trigger` names, a variable of that name or not."""
    ran = await _setup(hass, _automation([OPENED, CLOSED]))

    await _run(
        hass, trigger="door_closed", variables={"trigger": {"id": "door_opened"}}
    )

    assert ran[0].data["id"] == "door_closed"


async def test_the_variables_of_the_trigger_are_there(hass: HomeAssistant) -> None:
    """A trigger's own `variables:` go into the run, like when it fires."""
    ran = await _setup(
        hass, _automation([{**OPENED, "variables": {"reason": "{{ trigger.id }}!"}}])
    )

    await _run(hass)

    assert ran[0].data["reason"] == "door_opened!"


BLUEPRINT = """
blueprint:
  name: Door
  domain: automation
  input:
    door_id:
      selector:
        text:
triggers:
  - trigger: event
    event_type: knock
  - trigger: event
    event_type: door
    id: !input door_id
actions:
  - event: spook_ran
    event_data:
      branch: blueprint
      id: "{{ trigger.id }}"
      idx: "{{ trigger.idx }}"
"""


async def test_a_blueprint_automation_runs_by_its_filled_in_triggers(
    hass: HomeAssistant,
    tmp_path: Path,
) -> None:
    """The trigger IDs are those the inputs fill in, not the `!input` tags."""
    hass.config.config_dir = str(tmp_path)
    blueprint = tmp_path / "blueprints" / "automation" / "frenck" / "door.yaml"
    blueprint.parent.mkdir(parents=True)
    blueprint.write_text(BLUEPRINT, encoding="utf-8")

    ran = await _setup(
        hass,
        {
            "id": "front_door",
            "alias": "Front door",
            "use_blueprint": {
                "path": "frenck/door.yaml",
                "input": {"door_id": "door_opened"},
            },
        },
    )

    await _run(hass, trigger="door_opened")

    assert {"id": "door_opened", "idx": 1}.items() <= ran[0].data.items()


async def test_an_automation_that_failed_to_set_up_is_left_alone(
    hass: HomeAssistant,
) -> None:
    """Home Assistant never hands Spook an unavailable automation.

    It drops every unavailable entity from an entity action before the
    action sees it. So the run never starts, and asking for a response gets
    Home Assistant's own error, not one of Spook's.
    """
    broken = _automation([{"trigger": "ghost.appeared"}])
    ran = await _setup(hass, broken)
    assert hass.states.get(FRONT_DOOR).state == "unavailable"

    with pytest.raises(HomeAssistantError, match="did not match any entities"):
        await _run(hass)

    await hass.services.async_call(
        "automation", "run", {"entity_id": FRONT_DOOR}, blocking=True
    )
    assert not ran


async def test_the_response_is_per_automation(hass: HomeAssistant) -> None:
    """Each automation targeted says whether it ran."""
    other = {
        "id": "other",
        "alias": "Other",
        "triggers": [OPENED],
        "conditions": [{"condition": "template", "value_template": "{{ false }}"}],
        "actions": [REPORT],
    }
    await _setup(hass, _automation([OPENED]), other)

    response = await hass.services.async_call(
        "automation",
        "run",
        {"entity_id": [FRONT_DOOR, "automation.other"]},
        blocking=True,
        return_response=True,
    )

    assert response == {FRONT_DOOR: {"ran": True}, "automation.other": {"ran": False}}


async def test_a_run_turned_away_by_its_mode_did_not_run(hass: HomeAssistant) -> None:
    """A single-mode automation already running does not start a second run."""
    busy = _automation([OPENED])
    busy["actions"] = [{"wait_template": "{{ false }}"}]
    await _setup(hass, busy)

    first = hass.async_create_background_task(
        hass.services.async_call(
            "automation",
            "run",
            {"entity_id": FRONT_DOOR},
            blocking=True,
            return_response=True,
        ),
        "the first run",
    )
    # Not waiting for everything to be done: that is never, for this run.
    for _ in range(10):
        await asyncio.sleep(0)
    assert hass.states.get(FRONT_DOOR).attributes["current"] == 1

    assert await hass.services.async_call(
        "automation",
        "run",
        {"entity_id": FRONT_DOOR},
        blocking=True,
        return_response=True,
    ) == {FRONT_DOOR: {"ran": False}}

    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": FRONT_DOOR}, blocking=True
    )
    assert await first == {FRONT_DOOR: {"ran": True}}


async def test_the_context_is_passed_through(hass: HomeAssistant) -> None:
    """The run is a child of the call, like a run of Core's own action."""
    await _setup(hass, _automation([OPENED]))
    triggered = async_capture_events(hass, EVENT_AUTOMATION_TRIGGERED)

    asked = Context()
    await hass.services.async_call(
        "automation", "run", {"entity_id": FRONT_DOOR}, blocking=True, context=asked
    )
    await hass.async_block_till_done()

    assert triggered[0].context.parent_id == asked.id
    assert triggered[0].data["source"] == "action automation.run"


async def test_an_automation_that_is_off_runs_too(hass: HomeAssistant) -> None:
    """Like with Core's own action: off stops its triggers, not a run asked for."""
    ran = await _setup(hass, _automation([OPENED]), state="off")
    assert hass.states.get(FRONT_DOOR).state == "off"

    assert await _run(hass) == {FRONT_DOOR: {"ran": True}}
    assert len(ran) == 1
    assert hass.states.get(FRONT_DOOR).state == "off"
