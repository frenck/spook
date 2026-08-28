"""Tests for the spook.flapping trigger."""

# The tracker's own bookkeeping is what one of these is about, and there is
# no public way at it.
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.helpers.target import TargetSelection
from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers import (
    flapping as flapping_module,
)
from custom_components.spook.ectoplasms.spook.triggers.flapping import SpookTrigger
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

FLAPPER = "binary_sensor.dodgy"
WITHIN = timedelta(minutes=5)

TWICE = 2
THRICE = 3


async def _automation(
    hass: HomeAssistant,
    target: dict | None = None,
    options: dict[str, Any] | None = None,
) -> list[dict]:
    """Set up an automation on the trigger and record every run."""
    runs: list[dict] = []

    async def _mark(call) -> None:  # noqa: ANN001
        runs.append(dict(call.data))

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "unsettled",
                    "trigger": {
                        "platform": "spook.flapping",
                        "target": target or {"entity_id": FLAPPER},
                        "options": options or {"changes": 3, "within": "00:05:00"},
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "entity_id": "{{ trigger.entity_id }}",
                                "changes": "{{ trigger.changes }}",
                                "to_state": "{{ trigger.to_state.state }}",
                            },
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return runs


async def _detach(hass: HomeAssistant) -> None:
    """Turn the automation off, which detaches its trigger.

    The harness fails a test that leaves a listener behind, so this doubles as
    a check that it clears up.
    """
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "automation.unsettled"}, blocking=True
    )
    await hass.async_block_till_done()


async def _flap(
    hass: HomeAssistant,
    times: int,
    entity_id: str = FLAPPER,
    **kwargs: Any,
) -> None:
    """Change an entity's state `times` times.

    Toggling from wherever it is now, rather than from a fixed first value.
    Starting from "on" when it is already on writes the same state, which is
    not a change at all, and a test that thinks it made three changes and
    made two is a test that lies about what it proved.
    """
    for _ in range(times):
        current = hass.states.get(entity_id)
        following = "off" if current is not None and current.state == "on" else "on"
        hass.states.async_set(entity_id, following, **kwargs)
        await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "flapping" in await async_get_triggers(hass)


async def test_it_fires_on_the_change_that_tips_it_over(
    hass: HomeAssistant,
) -> None:
    """Three changes in five minutes, and the third is the one."""
    hass.states.async_set(FLAPPER, "off")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    await _flap(hass, 2)
    assert not runs, "fired before it had seen enough"

    await _flap(hass, 1)

    assert len(runs) == 1
    assert runs[0]["entity_id"] == FLAPPER
    assert runs[0]["changes"] == THRICE

    await _detach(hass)


async def test_changes_spread_out_are_not_flapping(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The window slides, so old changes stop counting."""
    hass.states.async_set(FLAPPER, "off")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    for _ in range(4):
        await _flap(hass, 1)
        freezer.tick(WITHIN)

    assert not runs, "changes minutes apart were called flapping"

    await _detach(hass)


async def test_it_does_not_report_the_same_spell_twice(
    hass: HomeAssistant,
) -> None:
    """A storm of alerts about a storm is worse than the storm."""
    hass.states.async_set(FLAPPER, "off")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    await _flap(hass, 10)

    assert len(runs) == 1, "it reported every change once it got going"

    await _detach(hass)


async def test_it_reports_again_once_it_has_settled(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Settling down and starting again is news a second time."""
    hass.states.async_set(FLAPPER, "off")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    await _flap(hass, 3)
    assert len(runs) == 1

    # Quiet for long enough that the old changes fall outside the window.
    freezer.tick(WITHIN * 2)
    await _flap(hass, 3)

    assert len(runs) == TWICE, "it never reported the second spell"

    await _detach(hass)


async def test_attribute_changes_do_not_count(hass: HomeAssistant) -> None:
    """Chatty is not the same as unsettled."""
    hass.states.async_set(FLAPPER, "on")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    for value in range(5):
        hass.states.async_set(FLAPPER, "on", {"brightness": value})
        await hass.async_block_till_done()

    assert not runs, "an entity holding one state was called flapping"

    await _detach(hass)


async def test_going_unavailable_and_back_counts(hass: HomeAssistant) -> None:
    """Which is the case this exists for."""
    hass.states.async_set(FLAPPER, "on")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    for state in ("unavailable", "on", "unavailable"):
        hass.states.async_set(FLAPPER, state)
        await hass.async_block_till_done()

    assert len(runs) == 1
    assert runs[0]["to_state"] == "unavailable"

    await _detach(hass)


async def test_an_entity_appearing_is_not_flapping(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Nor is one being removed, however often it happens.

    The log is checked as well as the runs, because those two failures look
    the same from the outside. Reading the state off a removal, where there is
    none to read, raises inside the event dispatch; Home Assistant swallows
    that and the trigger stays quiet, so "it did not fire" is true either way.
    """
    runs = await _automation(hass)

    for _ in range(5):
        hass.states.async_set(FLAPPER, "on")
        await hass.async_block_till_done()
        hass.states.async_remove(FLAPPER)
        await hass.async_block_till_done()

    assert not runs, "an entity coming and going was called flapping"
    assert not [
        record for record in caplog.records if record.levelno >= logging.ERROR
    ], "it went looking for a state that was not there"

    await _detach(hass)


async def test_an_entity_leaving_the_target_is_forgotten(
    hass: HomeAssistant,
) -> None:
    """Otherwise what it did is remembered for as long as the trigger lives.

    Checked on the tracker, because a target losing an entity is a registry
    event away and what it costs is memory rather than a wrong answer.
    """
    hass.states.async_set(FLAPPER, "off")
    await hass.async_block_till_done()

    tracker = flapping_module._FlappingEntityTracker(  # noqa: SLF001
        hass,
        TargetSelection({"entity_id": FLAPPER}),
        3,
        WITHIN,
        lambda _entity_id, _event: None,
    )
    stop = await tracker.async_setup()

    try:
        await _flap(hass, 2)
        assert FLAPPER in tracker._recent, "nothing was counted"  # noqa: SLF001

        tracker._handle_entities_update(set())  # noqa: SLF001
        assert not tracker._recent, (  # noqa: SLF001
            "it still remembers an entity it stopped watching"
        )
    finally:
        stop()
        await hass.async_block_till_done()


async def test_entities_are_counted_apart(hass: HomeAssistant) -> None:
    """Two entities each changing twice is not one changing four times."""
    other = "binary_sensor.also_dodgy"
    hass.states.async_set(FLAPPER, "off")
    hass.states.async_set(other, "off")
    await hass.async_block_till_done()

    runs = await _automation(hass, target={"entity_id": [FLAPPER, other]})

    await _flap(hass, 2)
    await _flap(hass, 2, entity_id=other)
    assert not runs, "changes to different entities were added together"

    await _flap(hass, 1)
    assert len(runs) == 1
    assert runs[0]["entity_id"] == FLAPPER

    await _detach(hass)


async def test_it_carries_the_change_that_tipped_it_over(
    hass: HomeAssistant,
) -> None:
    """Whoever made that change set the run going."""
    user = await hass.auth.async_create_user("Ghost Hunter")
    hass.states.async_set(FLAPPER, "off")
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
                    "alias": which,
                    "trigger": {
                        "platform": "spook.flapping",
                        "target": {"entity_id": FLAPPER},
                        "options": {"changes": 3, "within": "00:05:00"},
                    },
                    "condition": [{"condition": f"spook.{which}"}],
                    "action": [{"action": "test.mark", "data": {"which": which}}],
                }
                for which in ("triggered_by_user", "not_triggered_by_user")
            ]
        },
    )
    await hass.async_block_till_done()

    await _flap(hass, 2)
    hass.states.async_set(FLAPPER, "on", context=Context(user_id=user.id))
    await hass.async_block_till_done()

    assert ran == ["triggered_by_user"]

    for alias in ("triggered_by_user", "not_triggered_by_user"):
        await hass.services.async_call(
            "automation",
            "turn_off",
            {"entity_id": f"automation.{alias}"},
            blocking=True,
        )
    await hass.async_block_till_done()


async def test_one_change_is_not_flapping(hass: HomeAssistant) -> None:
    """It takes going back and forth, which needs at least two."""
    with pytest.raises(vol.Invalid, match="at least 2 changes"):
        await SpookTrigger.async_validate_config(
            hass,
            {
                "target": {"entity_id": FLAPPER},
                "options": {"changes": 1, "within": "00:05:00"},
            },
        )


async def test_a_zero_window_is_refused(hass: HomeAssistant) -> None:
    """Nothing can happen inside no time at all."""
    with pytest.raises(vol.Invalid, match="longer than zero"):
        await SpookTrigger.async_validate_config(
            hass,
            {
                "target": {"entity_id": FLAPPER},
                "options": {"changes": 3, "within": {"seconds": 0}},
            },
        )


async def test_an_empty_target_is_refused(hass: HomeAssistant) -> None:
    """It would load and then watch nothing at all."""
    with pytest.raises(vol.Invalid, match="at least one entity"):
        await SpookTrigger.async_validate_config(
            hass,
            {"target": {}, "options": {"changes": 3, "within": "00:05:00"}},
        )


async def test_both_options_are_required(hass: HomeAssistant) -> None:
    """Neither has a sensible default to fall back on."""
    for options in ({"changes": 3}, {"within": "00:05:00"}):
        with pytest.raises(vol.Invalid, match="required key"):
            await SpookTrigger.async_validate_config(
                hass, {"target": {"entity_id": FLAPPER}, "options": options}
            )


async def test_an_absurd_number_of_changes_is_refused(hass: HomeAssistant) -> None:
    """The count is also how many moments are kept per entity.

    The number selector offers a thousand as its ceiling, so written
    configuration has to stop there too, or the interface promises a limit
    that YAML walks straight around.
    """
    with pytest.raises(vol.Invalid, match="not looking for a flapping entity"):
        await SpookTrigger.async_validate_config(
            hass,
            {
                "target": {"entity_id": FLAPPER},
                "options": {"changes": 1001, "within": "00:05:00"},
            },
        )


async def test_a_second_spell_that_starts_straight_away_is_reported(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Settling and starting again inside one window's worth of quiet.

    Three changes, then quiet for long enough that they no longer count, then
    three more in quick succession. The third of those completes a window of
    its own and is a spell in its own right.
    """
    hass.states.async_set(FLAPPER, "off")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    await _flap(hass, 3)
    assert len(runs) == 1

    freezer.tick(WITHIN * 3)

    # The first two of the new spell still have an old change in hand, so it
    # is the third that completes a window made only of new ones.
    await _flap(hass, 2)
    assert len(runs) == 1, "it reported before it had a whole new window"

    await _flap(hass, 1)
    assert len(runs) == TWICE, "the second spell went unreported"

    await _detach(hass)


async def test_carrying_on_flapping_is_still_one_spell(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A change late in the window continues a spell rather than starting one.

    Three changes a minute apart fire once. A fourth four minutes later still
    leaves the last three inside a five minute window, so the entity has not
    settled and there is nothing new to say.
    """
    hass.states.async_set(FLAPPER, "off")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    for _ in range(3):
        await _flap(hass, 1)
        freezer.tick(timedelta(minutes=1))
    assert len(runs) == 1

    freezer.tick(timedelta(minutes=3))
    await _flap(hass, 1)

    assert len(runs) == 1, "a spell that never let up was reported twice"

    await _detach(hass)
