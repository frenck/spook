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
