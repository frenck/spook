"""Tests for the spook.triggered_by_automation condition."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

from homeassistant.core import Context
from homeassistant.helpers.condition import ConditionConfig
from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.automation_runs import (
    CACHE_SIZE,
    AutomationRuns,
    async_get_automation_runs,
)
from custom_components.spook.ectoplasms.spook.conditions.triggered_by_automation import (
    SpookCondition,
)

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _house(hass: HomeAssistant, options: dict | None = None) -> list[str]:
    """Set up an upstream automation, a script, and a guarded downstream one.

    The downstream automation reacts to a switch and only runs its action when
    the condition passes, so the returned list says what got through.
    """
    ran: list[str] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["by"])

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"switch": None}}
    )
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "middleman": {
                    "sequence": [
                        {
                            "action": "input_boolean.turn_on",
                            "target": {"entity_id": "input_boolean.switch"},
                        }
                    ]
                }
            }
        },
    )
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "upstream",
                    "trigger": {"platform": "event", "event_type": "flip"},
                    "action": [
                        {
                            "action": "input_boolean.turn_on",
                            "target": {"entity_id": "input_boolean.switch"},
                        }
                    ],
                },
                {
                    "alias": "upstream via script",
                    "trigger": {"platform": "event", "event_type": "flip_via_script"},
                    "action": [{"action": "script.middleman"}],
                },
                {
                    "alias": "downstream",
                    "trigger": {
                        "platform": "state",
                        "entity_id": "input_boolean.switch",
                        "to": "on",
                    },
                    "condition": [
                        {
                            "condition": "spook.triggered_by_automation",
                            **({"options": options} if options else {}),
                        }
                    ],
                    "action": [{"action": "test.mark", "data": {"by": "automation"}}],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def _reset(hass: HomeAssistant) -> None:
    """Put the switch back, without anybody's context attached."""
    hass.states.async_set("input_boolean.switch", "off")
    await hass.async_block_till_done()


async def test_it_passes_when_an_automation_caused_the_change(
    hass: HomeAssistant,
) -> None:
    """The plain case: one automation writes, another reacts."""
    ran = await _house(hass)

    hass.bus.async_fire("flip")
    await hass.async_block_till_done()

    assert ran == ["automation"]


async def test_it_passes_through_a_script(hass: HomeAssistant) -> None:
    """A script in between keeps the automation's context, so it still counts.

    The script does the writing, but it runs under the automation's context,
    so the change still points back at the automation that started it.
    """
    ran = await _house(hass)

    hass.bus.async_fire("flip_via_script")
    await hass.async_block_till_done()

    assert ran == ["automation"]


async def test_it_fails_when_nothing_caused_the_change(hass: HomeAssistant) -> None:
    """A write from nowhere is not an automation."""
    ran = await _house(hass)

    hass.states.async_set("input_boolean.switch", "on")
    await hass.async_block_till_done()

    assert not ran


async def test_it_can_be_narrowed_to_one_automation(hass: HomeAssistant) -> None:
    """Naming an automation accepts that one and turns the others down."""
    ran = await _house(hass, {"automation": ["automation.upstream"]})

    hass.bus.async_fire("flip")
    await hass.async_block_till_done()
    assert ran == ["automation"]

    await _reset(hass)
    ran.clear()

    hass.bus.async_fire("flip_via_script")
    await hass.async_block_till_done()
    assert not ran, "accepted an automation that was not named"


async def test_a_named_automation_still_counts_through_a_script(
    hass: HomeAssistant,
) -> None:
    """Narrowing follows the chain too, and names the automation, not the script."""
    ran = await _house(hass, {"automation": ["automation.upstream_via_script"]})

    hass.bus.async_fire("flip_via_script")
    await hass.async_block_till_done()

    assert ran == ["automation"]


async def test_a_non_automation_entity_is_refused(hass: HomeAssistant) -> None:
    """The option only takes automations."""
    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(
            hass, {"options": {"automation": ["light.kitchen"]}}
        )


async def test_no_options_is_fine(hass: HomeAssistant) -> None:
    """Asking about any automation at all needs no options."""
    assert await SpookCondition.async_validate_config(hass, {}) == {"options": {}}


async def test_checking_after_unloading_says_no_rather_than_falling_over(
    hass: HomeAssistant,
) -> None:
    """Home Assistant does not stop anybody checking an unloaded condition.

    So this has to answer rather than break. The register lets go of its
    listener and its memory, which makes the answer no.
    """
    condition = SpookCondition(hass, ConditionConfig(options={}))
    await condition.async_setup()

    hass.bus.async_fire(
        "automation_triggered",
        {"entity_id": "automation.goodnight"},
        context=Context(id="a-run"),
    )
    await hass.async_block_till_done()

    variables = {"trigger": {"to_state": Mock(context=Context(id="a-run"))}}
    assert condition.async_check(variables=variables) is True

    condition.async_unload()

    assert condition.async_check(variables=variables) is False


async def test_the_register_stops_listening_when_the_last_user_leaves(
    hass: HomeAssistant,
) -> None:
    """One shared listener, reference counted, and no listener left behind.

    Every condition instance wants the same mapping, so they share it. The
    listener has to survive one of them unloading and go away with the last.
    """
    runs = async_get_automation_runs(hass)
    assert async_get_automation_runs(hass) is runs, "made a second register"

    def _listeners() -> int:
        return len(hass.bus.async_listeners().keys() & {"automation_triggered"})

    assert _listeners() == 0

    runs.async_acquire()
    runs.async_acquire()
    assert _listeners() == 1, "one listener for however many askers"

    runs.async_release()
    assert _listeners() == 1, "let go too early, with a user left"

    runs.async_release()
    assert _listeners() == 0, "left a listener behind"

    # And it comes back for the next one.
    runs.async_acquire()
    assert _listeners() == 1
    runs.async_release()


async def test_the_register_forgets_the_oldest_runs(hass: HomeAssistant) -> None:
    """The mapping is bounded: every automation run would otherwise add one.

    Only a run from a moment ago is ever asked about, so dropping the oldest
    costs nothing and keeps a busy house from growing this forever.
    """
    runs = AutomationRuns(hass)
    runs.async_acquire()

    overflow = 10
    for index in range(CACHE_SIZE + overflow):
        hass.bus.async_fire(
            "automation_triggered",
            {"entity_id": f"automation.number_{index}"},
            context=Context(id=f"run-{index}"),
        )
    await hass.async_block_till_done()

    # The newest runs are all still there.
    for index in range(CACHE_SIZE + overflow - 5, CACHE_SIZE + overflow):
        assert runs.async_which(f"run-{index}") == f"automation.number_{index}"

    # The oldest have been dropped to make room, which is the whole point.
    for index in range(overflow):
        assert runs.async_which(f"run-{index}") is None, f"run-{index} was kept"

    runs.async_release()
