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

from custom_components.spook.automation_runs import (
    CACHE_SIZE,
    AutomationRuns,
    async_get_automation_runs,
    async_setup_automation_runs,
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


async def test_a_context_that_is_not_the_one_asked_about_is_not_the_end_of_it(
    hass: HomeAssistant,
) -> None:
    """A near context naming the wrong automation must not settle the answer.

    Several contexts can be in reach at once, and only one of them needs to
    be the automation somebody asked about. Reading the nearest and returning
    its verdict reports no whenever anything else got there first.
    """
    runs = async_get_automation_runs(hass)
    hass.bus.async_fire(
        "automation_triggered",
        {"entity_id": "automation.somebody_else"},
        context=Context(id="near"),
    )
    hass.bus.async_fire(
        "automation_triggered",
        {"entity_id": "automation.wanted"},
        context=Context(id="further"),
    )
    await hass.async_block_till_done()
    assert runs.async_which("near") == "automation.somebody_else"

    condition = SpookCondition(
        hass, ConditionConfig(options={"automation": ["automation.wanted"]})
    )
    await condition.async_setup()

    variables = {
        "context": Context(id="near"),
        "trigger": {"to_state": Mock(context=Context(id="further"))},
    }

    assert condition.async_check(variables=variables) is True


async def test_the_register_is_shared_and_listening(hass: HomeAssistant) -> None:
    """One register for the whole integration, already listening."""
    runs = async_get_automation_runs(hass)
    assert async_get_automation_runs(hass) is runs, "made a second register"

    hass.bus.async_fire(
        "automation_triggered",
        {"entity_id": "automation.goodnight"},
        context=Context(id="a-run"),
    )
    await hass.async_block_till_done()

    assert runs.async_which("a-run") == "automation.goodnight"


async def test_stopping_the_register_lets_go_of_everything(
    hass: HomeAssistant,
) -> None:
    """Setting it up hands back the way to stop, and stopping really stops."""
    stop = async_setup_automation_runs(hass)
    runs = async_get_automation_runs(hass)

    hass.bus.async_fire(
        "automation_triggered",
        {"entity_id": "automation.goodnight"},
        context=Context(id="a-run"),
    )
    await hass.async_block_till_done()
    assert runs.async_which("a-run") == "automation.goodnight"

    stop()

    assert runs.async_which("a-run") is None, "kept what it was told to forget"
    assert "automation_triggered" not in hass.bus.async_listeners()

    hass.bus.async_fire(
        "automation_triggered",
        {"entity_id": "automation.goodnight"},
        context=Context(id="another-run"),
    )
    await hass.async_block_till_done()
    assert runs.async_which("another-run") is None, "carried on listening"


async def test_the_register_forgets_the_oldest_runs(hass: HomeAssistant) -> None:
    """The mapping is bounded: every automation run would otherwise add one.

    Only a run from a moment ago is ever asked about, so dropping the oldest
    costs nothing and keeps a busy house from growing this forever.
    """
    runs = AutomationRuns(hass)
    runs.async_start()

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

    runs.async_stop()


async def _guarded_actions(
    hass: HomeAssistant, options: dict | None = None
) -> list[str]:
    """Put the condition inside an action sequence, where the docs send people.

    That placement is the one that matters for a forced run, and it is also
    where the automation's own context is closest to hand.
    """
    ran: list[str] = []

    # Spook starts this in its own setup, and it has to be running before the
    # automations do: a condition inside an action sequence is only built once
    # that sequence runs, which is after the automation announced itself.
    async_setup_automation_runs(hass)

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["verdict"])

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"switch": None}}
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
                    "alias": "asker",
                    "trigger": [
                        {"platform": "event", "event_type": "ask"},
                        {
                            "platform": "state",
                            "entity_id": "input_boolean.switch",
                            "to": "on",
                        },
                    ],
                    "action": [
                        {
                            "if": [
                                {
                                    "condition": "spook.triggered_by_automation",
                                    **({"options": options} if options else {}),
                                }
                            ],
                            "then": [
                                {"action": "test.mark", "data": {"verdict": "passed"}}
                            ],
                            "else": [
                                {"action": "test.mark", "data": {"verdict": "failed"}}
                            ],
                        }
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def test_it_does_not_count_the_automation_doing_the_asking(
    hass: HomeAssistant,
) -> None:
    """Inside an action sequence the run's own context is the nearest one.

    The register knows it, because the automation announced itself on the way
    in. Counting it would make this pass for a bare event, a schedule or a
    person, which is the opposite of what it is for.
    """
    ran = await _guarded_actions(hass)

    hass.bus.async_fire("ask")
    await hass.async_block_till_done()

    assert ran == ["failed"], "counted itself as the automation that fired it"


async def test_it_finds_the_upstream_automation_from_inside_the_actions(
    hass: HomeAssistant,
) -> None:
    """Skipping itself must not stop the search at the first context.

    Narrowed to the upstream automation, the nearest context is this run's own
    and the next one out is the answer. Settling for the first would report no.
    """
    ran = await _guarded_actions(hass, {"automation": ["automation.upstream"]})

    hass.bus.async_fire("flip")
    await hass.async_block_till_done()

    assert ran == ["passed"], "gave up before reaching the automation upstream"
