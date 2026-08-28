"""Tests for the spook.quota condition."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.condition import ConditionConfig
from homeassistant.components.script.const import EVENT_SCRIPT_STARTED
from homeassistant.core import Context
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
import voluptuous as vol

from custom_components.spook.condition import async_get_conditions
from custom_components.spook.ectoplasms.spook.conditions.quota import SpookCondition
from custom_components.spook.run_history import (
    MAX_RUNS_REMEMBERED,
    async_get_run_history,
    async_setup_run_history,
)

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

ALLOWANCE = 2
THREE = 3
FIVE = 5


if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant


async def _automation(
    hass: HomeAssistant,
    limit: int = 2,
    period: str = "01:00:00",
    extra_conditions: list[dict] | None = None,
) -> list[str]:
    """Set up an automation guarded by a quota, and record what got through."""
    ran: list[str] = []

    # Spook starts this in its own setup, and it has to be running before
    # anything runs: it is what remembers the runs being counted.
    async_setup_run_history(hass)

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["at"])

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "rationed",
                    "trigger": {"platform": "event", "event_type": "kick"},
                    "condition": [
                        *(extra_conditions or []),
                        {
                            "condition": "spook.quota",
                            "options": {"limit": limit, "period": period},
                        },
                    ],
                    "action": [{"action": "test.mark", "data": {"at": "{{ now() }}"}}],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def _kick(hass: HomeAssistant, times: int = 1) -> None:
    """Set the automation off, and let it settle."""
    for _ in range(times):
        hass.bus.async_fire("kick")
        await hass.async_block_till_done()


async def test_the_condition_is_discovered(hass: HomeAssistant) -> None:
    """The condition turns up in Spook's discovery, under a plain key."""
    assert "quota" in await async_get_conditions(hass)


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"limit": 5},
        {"period": "01:00:00"},
        {"limit": 0, "period": "01:00:00"},
        {"limit": -1, "period": "01:00:00"},
        {"limit": 5, "period": "00:00:00"},
    ],
)
async def test_a_nonsense_allowance_is_refused(
    hass: HomeAssistant,
    options: dict,
) -> None:
    """Both options are required, and neither can be zero.

    A limit of zero never passes and a period of zero always does, so both
    are ways of writing a condition that does not do anything.
    """
    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(hass, {"options": options})


@pytest.mark.parametrize("limit", [1.5, 0.5, "5.5", True, False, "five", None])
async def test_a_limit_that_is_not_a_whole_count_is_refused(
    hass: HomeAssistant,
    limit: object,
) -> None:
    """An allowance is a number of runs, so half a run is not one.

    Coercing would hand back 1 for both 1.5 and `True`, so a mistyped limit
    would quietly become a different one. And only half quietly: 0.5 already
    landed below the minimum and was refused, which made the silent half
    inconsistent as well as wrong.
    """
    with pytest.raises(vol.Invalid, match="whole number"):
        await SpookCondition.async_validate_config(
            hass, {"options": {"limit": limit, "period": "01:00:00"}}
        )


@pytest.mark.parametrize("limit", [5, "5", 5.0])
async def test_a_whole_count_is_accepted_however_it_is_written(
    hass: HomeAssistant,
    limit: object,
) -> None:
    """YAML hands numbers over in more than one shape, and all of these are five."""
    validated = await SpookCondition.async_validate_config(
        hass, {"options": {"limit": limit, "period": "01:00:00"}}
    )

    assert validated["options"]["limit"] == FIVE


async def test_a_limit_beyond_what_is_remembered_is_refused(
    hass: HomeAssistant,
) -> None:
    """The history is bounded, so a limit above it could never be answered."""
    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(
            hass,
            {"options": {"limit": MAX_RUNS_REMEMBERED + 1, "period": "01:00:00"}},
        )


async def test_it_allows_the_limit_and_then_stops(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Two an hour means two, and the third is turned down."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    ran = await _automation(hass, limit=2, period="01:00:00")

    await _kick(hass, 5)

    assert len(ran) == ALLOWANCE, f"let {len(ran)} through on an allowance of two"


async def test_the_allowance_comes_back_as_the_window_rolls(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The window rolls rather than resetting on the hour.

    Two runs at noon and the allowance is back at one minute past one, not at
    one o'clock sharp, because that is when the first of them leaves the last
    hour.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    ran = await _automation(hass, limit=2, period="01:00:00")

    await _kick(hass, 3)
    assert len(ran) == ALLOWANCE

    freezer.tick(timedelta(minutes=59))
    await _kick(hass)
    assert len(ran) == ALLOWANCE, "let one through before the window had rolled"

    freezer.tick(timedelta(minutes=2))
    await _kick(hass)
    assert len(ran) == THREE, "allowance never came back"


async def test_a_run_something_else_turned_down_costs_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Only runs that really happened count against the allowance.

    Home Assistant does not announce an automation whose conditions turned the
    run down, which is what makes this true, so it is worth pinning: a blocked
    run must not quietly eat somebody's allowance.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"gate": None}}
    )
    hass.states.async_set("input_boolean.gate", "off")

    ran = await _automation(
        hass,
        limit=2,
        period="01:00:00",
        extra_conditions=[
            {
                "condition": "state",
                "entity_id": "input_boolean.gate",
                "state": "on",
            }
        ],
    )

    # Five attempts, all held back by the gate rather than by the quota.
    await _kick(hass, 5)
    assert not ran

    hass.states.async_set("input_boolean.gate", "on")
    await _kick(hass, 3)

    assert len(ran) == ALLOWANCE, "the blocked attempts ate into the allowance"


async def test_it_counts_per_automation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """One automation using up its allowance does not spend another's."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    async_setup_run_history(hass)

    ran: list[str] = []
    hass.services.async_register(
        "test", "mark", lambda call: ran.append(call.data["who"])
    )

    def _automation_config(name: str, event: str) -> dict:
        return {
            "alias": name,
            "trigger": {"platform": "event", "event_type": event},
            "condition": [
                {
                    "condition": "spook.quota",
                    "options": {"limit": 1, "period": "01:00:00"},
                }
            ],
            "action": [{"action": "test.mark", "data": {"who": name}}],
        }

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                _automation_config("first", "kick_first"),
                _automation_config("second", "kick_second"),
            ]
        },
    )
    await hass.async_block_till_done()

    for _ in range(3):
        hass.bus.async_fire("kick_first")
        await hass.async_block_till_done()

    assert ran == ["first"]

    hass.bus.async_fire("kick_second")
    await hass.async_block_till_done()

    assert ran == ["first", "second"], "one automation spent the other's allowance"


async def test_it_counts_scripts_too(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A script has an allowance as well, the same as `cooldown` covers both."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    async_setup_run_history(hass)

    ran: list[int] = []
    hass.services.async_register("test", "mark", lambda _call: ran.append(1))

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "rationed": {
                    "sequence": [
                        {
                            "if": [
                                {
                                    "condition": "spook.quota",
                                    "options": {"limit": 1, "period": "01:00:00"},
                                }
                            ],
                            "then": [{"action": "test.mark"}],
                        }
                    ]
                }
            }
        },
    )
    await hass.async_block_till_done()

    for _ in range(3):
        await hass.services.async_call("script", "rationed", blocking=True)
        await hass.async_block_till_done()

    assert len(ran) == 1, f"let {len(ran)} through on an allowance of one"


async def test_repeated_calls_sharing_a_context_still_spend_the_allowance(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A script inherits its caller's context, so runs can share one.

    An automation calling the same script three times over gives all three
    runs the same context. Leaving out every run under the current context
    rather than only the current run would mean this script never spent
    anything at all.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    async_setup_run_history(hass)

    ran: list[int] = []
    hass.services.async_register("test", "mark", lambda _call: ran.append(1))

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "rationed": {
                    "sequence": [
                        {
                            "if": [
                                {
                                    "condition": "spook.quota",
                                    "options": {"limit": 1, "period": "01:00:00"},
                                }
                            ],
                            "then": [{"action": "test.mark"}],
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
                    "alias": "caller",
                    "trigger": {"platform": "event", "event_type": "kick"},
                    "action": [
                        {
                            "repeat": {
                                "count": 3,
                                "sequence": [{"action": "script.rationed"}],
                            }
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire("kick")
    await hass.async_block_till_done()

    assert len(ran) == 1, f"let {len(ran)} through on an allowance of one"


async def test_the_history_keeps_room_for_the_run_doing_the_asking(
    hass: HomeAssistant,
) -> None:
    """The current run must not push the oldest run being counted out of reach.

    A script's run is remembered before its condition is checked, so with only
    as many slots as the largest allowance the oldest of them would be gone by
    the time anybody counted. A limit of 64 could then never be reached.
    """
    async_setup_run_history(hass)
    history = async_get_run_history(hass)

    for index in range(MAX_RUNS_REMEMBERED):
        hass.bus.async_fire(
            EVENT_SCRIPT_STARTED,
            {"entity_id": "script.busy"},
            context=Context(id=f"prior-{index}"),
        )
    await hass.async_block_till_done()

    # And now the run that is about to ask, arriving before the check.
    hass.bus.async_fire(
        EVENT_SCRIPT_STARTED,
        {"entity_id": "script.busy"},
        context=Context(id="current"),
    )
    await hass.async_block_till_done()

    prior = history.async_runs_within(
        "script.busy", timedelta(hours=1), ignoring="current"
    )
    assert prior == MAX_RUNS_REMEMBERED, (
        f"only {prior} of {MAX_RUNS_REMEMBERED} prior runs left countable"
    )


async def test_it_passes_when_there_is_nothing_to_count_against(
    hass: HomeAssistant,
) -> None:
    """Checked outside an automation or script, there is no allowance to spend."""
    condition = SpookCondition(
        hass, ConditionConfig(options={"limit": 1, "period": timedelta(hours=1)})
    )
    await condition.async_setup()

    assert condition.async_check(variables={}) is True
