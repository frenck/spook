"""Tests for the context conditions where they are actually used.

These exist because the first version of this worked perfectly in a script
and did nothing at all in an automation. An automation does not inherit the
context of whatever set it off: it starts a fresh one carrying only a
parent_id (`components/automation/__init__.py`), and a top-level condition is
handed only `this` and `trigger`. So the user has to come out of the trigger,
and only a test at this level can tell you whether it does.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import Context
from homeassistant.setup import async_setup_component

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the condition
# platform. Without it these tests only pass when some other file in the run
# happened to import Spook first, which is a fine way to have a test suite that
# is green for the wrong reason.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _automations(hass: HomeAssistant, trigger: dict) -> list[str]:
    """Set up one automation per condition and report which ones run."""
    ran: list[str] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["which"])

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": which,
                    "trigger": trigger,
                    "condition": [{"condition": f"spook.{which}"}],
                    "action": [{"action": "test.mark", "data": {"which": which}}],
                }
                for which in ("triggered_by_user", "not_triggered_by_user")
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def test_an_event_fired_by_a_user(hass: HomeAssistant) -> None:
    """A user behind the event is found through the trigger."""
    ran = await _automations(hass, {"platform": "event", "event_type": "spook_test"})

    hass.bus.async_fire("spook_test", {}, context=Context(user_id="ghost-hunter"))
    await hass.async_block_till_done()

    assert ran == ["triggered_by_user"]


async def test_an_event_fired_by_nobody(hass: HomeAssistant) -> None:
    """An event with no user behind it is nobody's doing."""
    ran = await _automations(hass, {"platform": "event", "event_type": "spook_test"})

    hass.bus.async_fire("spook_test", {}, context=Context())
    await hass.async_block_till_done()

    assert ran == ["not_triggered_by_user"]


async def test_a_state_change_made_by_a_user(hass: HomeAssistant) -> None:
    """A state trigger carries its user in the state that changed."""
    ran = await _automations(
        hass, {"platform": "state", "entity_id": "input_boolean.spook_test"}
    )

    hass.states.async_set(
        "input_boolean.spook_test", "on", context=Context(user_id="ghost-hunter")
    )
    await hass.async_block_till_done()

    assert ran == ["triggered_by_user"]


async def test_a_state_change_made_by_an_integration(hass: HomeAssistant) -> None:
    """A state change nobody asked for is not a person's doing."""
    ran = await _automations(
        hass, {"platform": "state", "entity_id": "input_boolean.spook_test"}
    )

    hass.states.async_set("input_boolean.spook_test", "on")
    await hass.async_block_till_done()

    assert ran == ["not_triggered_by_user"]


async def test_inside_the_action_sequence(hass: HomeAssistant) -> None:
    """The conditions also work in an `if` inside the actions.

    Worth its own test: the action sequence runs under the automation's own
    fresh context, so this is a different code path from the top-level
    condition even though it reads the same in YAML.
    """
    ran: list[str] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["which"])

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "in the actions",
                    "trigger": {"platform": "event", "event_type": "spook_test"},
                    "action": [
                        {
                            "if": [{"condition": f"spook.{which}"}],
                            "then": [{"action": "test.mark", "data": {"which": which}}],
                        }
                        for which in ("triggered_by_user", "not_triggered_by_user")
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire("spook_test", {}, context=Context(user_id="ghost-hunter"))
    await hass.async_block_till_done()

    assert ran == ["triggered_by_user"]


async def test_an_earlier_user_is_not_blamed_for_a_later_change(
    hass: HomeAssistant,
) -> None:
    """A user's write must not be attributed to the integration write after it.

    The state a trigger moved away from carries the context of whoever wrote
    it. Reading that as the cause meant a user flipping a switch and an
    integration turning it back a minute later both looked like the user.
    """
    ran = await _automations(
        hass, {"platform": "state", "entity_id": "input_boolean.spook_test"}
    )

    hass.states.async_set(
        "input_boolean.spook_test", "on", context=Context(user_id="ghost-hunter")
    )
    await hass.async_block_till_done()
    assert ran == ["triggered_by_user"]

    ran.clear()
    hass.states.async_set("input_boolean.spook_test", "off")
    await hass.async_block_till_done()

    assert ran == ["not_triggered_by_user"]


async def test_forcing_a_run_is_attributed_to_nobody(hass: HomeAssistant) -> None:
    """Pressing "Run actions" cannot be pinned on the person who pressed it.

    Home Assistant hands the caller's account to the automation, but the run
    starts a fresh context carrying only a pointer back to the caller's, and
    nothing resolves that pointer. This is documented rather than worked
    around, so it is worth pinning: if a future Home Assistant does propagate
    it, this test fails and the documentation needs to change.
    """
    user = await hass.auth.async_create_user("Ghost Hunter", group_ids=["system-admin"])
    ran = await _automations(hass, {"platform": "event", "event_type": "never"})
    entities = [
        "automation.triggered_by_user",
        "automation.not_triggered_by_user",
    ]

    await hass.services.async_call(
        "automation",
        "trigger",
        {"entity_id": entities, "skip_condition": False},
        blocking=True,
        context=Context(user_id=user.id),
    )
    await hass.async_block_till_done()

    assert ran == ["not_triggered_by_user"]


async def test_the_run_button_skips_top_level_conditions_entirely(
    hass: HomeAssistant,
) -> None:
    """Pressing "Run actions" does not evaluate a top-level condition at all.

    `automation.trigger` defaults to `skip_condition: true`, so both of these
    automations run their actions regardless of what their condition would
    have said. That is Home Assistant's behaviour for every condition, and it
    is worth pinning because it makes the documented advice conditional: to
    recognise a forced run as nobody's doing, the condition has to sit inside
    the actions.
    """
    user = await hass.auth.async_create_user("Ghost Hunter", group_ids=["system-admin"])
    ran = await _automations(hass, {"platform": "event", "event_type": "never"})

    await hass.services.async_call(
        "automation",
        "trigger",
        {
            "entity_id": [
                "automation.triggered_by_user",
                "automation.not_triggered_by_user",
            ]
        },
        blocking=True,
        context=Context(user_id=user.id),
    )
    await hass.async_block_till_done()

    assert sorted(ran) == ["not_triggered_by_user", "triggered_by_user"]


async def test_excluding_a_person_needs_home_assistants_not(
    hass: HomeAssistant,
) -> None:
    """Excluding somebody means wrapping the condition, not swapping it.

    Naming a person makes `triggered_by_user` pass *for* them, so the
    documentation now points at Home Assistant's own `not` condition. That is
    advice, and advice deserves a test: it also shows that "not Frenck" covers
    the case where nobody was behind it at all.
    """
    frenck = await hass.auth.async_create_user("Frenck")
    joe = await hass.auth.async_create_user("Joe")
    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {"id": "frenck", "name": "Frenck", "user_id": frenck.id},
                {"id": "joe", "name": "Joe", "user_id": joe.id},
            ]
        },
    )
    await hass.async_block_till_done()

    ran: list[str] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["which"])

    hass.services.async_register("test", "mark", _mark)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "anyone but frenck",
                    "trigger": {
                        "platform": "state",
                        "entity_id": "input_boolean.spook_test",
                    },
                    "condition": [
                        {
                            "condition": "not",
                            "conditions": [
                                {
                                    "condition": "spook.triggered_by_user",
                                    "options": {"person": "person.frenck"},
                                }
                            ],
                        }
                    ],
                    "action": [
                        {"action": "test.mark", "data": {"which": "not-frenck"}}
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "input_boolean.spook_test", "on", context=Context(user_id=frenck.id)
    )
    await hass.async_block_till_done()
    assert not ran

    hass.states.async_set(
        "input_boolean.spook_test", "off", context=Context(user_id=joe.id)
    )
    await hass.async_block_till_done()
    assert ran == ["not-frenck"]

    ran.clear()
    hass.states.async_set("input_boolean.spook_test", "on")
    await hass.async_block_till_done()
    assert ran == ["not-frenck"]


async def test_a_template_trigger_inherits_the_change_behind_it(
    hass: HomeAssistant,
) -> None:
    """A template that became true because of a person is that person's doing.

    Home Assistant's template trigger hands over the state change that made
    the template flip, so the user behind that change comes through. Worth a
    test because it is not obvious from the outside, and because the
    documentation said the opposite until review pointed it out.
    """
    user = await hass.auth.async_create_user("Ghost Hunter")
    hass.states.async_set("input_boolean.spook_test", "off")
    await hass.async_block_till_done()

    ran = await _automations(
        hass,
        {
            "platform": "template",
            "value_template": "{{ is_state('input_boolean.spook_test', 'on') }}",
        },
    )

    hass.states.async_set(
        "input_boolean.spook_test", "on", context=Context(user_id=user.id)
    )
    await hass.async_block_till_done()
    assert ran == ["triggered_by_user"]

    # And an integration flipping it back and forth is nobody's doing.
    hass.states.async_set("input_boolean.spook_test", "off")
    await hass.async_block_till_done()
    ran.clear()
    hass.states.async_set("input_boolean.spook_test", "on")
    await hass.async_block_till_done()

    assert ran == ["not_triggered_by_user"]


async def test_a_condition_trigger_inherits_the_change_behind_it(
    hass: HomeAssistant,
) -> None:
    """Same for Spook's own condition trigger, for the same reason.

    A condition that turned true because a person flipped a switch is that
    person's doing, so the state change that made it turn has to come through.
    """
    user = await hass.auth.async_create_user("Ghost Hunter")
    hass.states.async_set("input_boolean.spook_test", "off")
    await hass.async_block_till_done()

    ran = await _automations(
        hass,
        {
            "platform": "spook.condition_met",
            "options": {
                "condition": {
                    "condition": "state",
                    "entity_id": "input_boolean.spook_test",
                    "state": "on",
                },
            },
        },
    )

    hass.states.async_set(
        "input_boolean.spook_test", "on", context=Context(user_id=user.id)
    )
    await hass.async_block_till_done()
    assert ran == ["triggered_by_user"]
