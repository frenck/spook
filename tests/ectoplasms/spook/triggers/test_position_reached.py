"""Tests for the spook.position_reached trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Context
from homeassistant.helpers.trigger import TriggerConfig
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.position_reached import (
    SpookTrigger,
)
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

BLINDS = "cover.blinds"


async def _attach(
    hass: HomeAssistant, position: int = 30, target: dict | None = None
) -> tuple[list[tuple[dict, Context | None]], Callable[[], None]]:
    """Attach the trigger, and record everything it hands over."""
    validated = await SpookTrigger.async_validate_config(
        hass,
        {"target": target or {"entity_id": BLINDS}, "options": {"position": position}},
    )
    handed: list[tuple[dict, Context | None]] = []
    trigger = SpookTrigger(
        hass,
        TriggerConfig(
            key="position_reached",
            target=validated["target"],
            options=validated["options"],
        ),
    )

    def _run(payload, _description, context=None) -> None:  # noqa: ANN001
        handed.append((payload, context))

    unsub = await trigger.async_attach_runner(_run)
    return handed, unsub


async def _at(
    hass: HomeAssistant,
    position: float | None,
    state: str = "open",
    entity_id: str = BLINDS,
    context: Context | None = None,
) -> None:
    """Write a position and let it be handled."""
    attributes = {} if position is None else {"current_position": position}
    hass.states.async_set(entity_id, state, attributes, context=context)
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "position_reached" in await async_get_triggers(hass)


@pytest.mark.parametrize("position", [-1, 101, 30.5, "half", True, None])
async def test_a_position_that_is_not_one_is_refused(
    hass: HomeAssistant, position: object
) -> None:
    """A whole percentage from closed to open, and not cut down to one."""
    with pytest.raises(vol.Invalid, match="position"):
        await SpookTrigger.async_validate_config(
            hass,
            {"target": {"entity_id": BLINDS}, "options": {"position": position}},
        )


@pytest.mark.parametrize("position", [0, 100, "30", 30.0])
async def test_a_position_from_closed_to_open_is_taken(
    hass: HomeAssistant, position: object
) -> None:
    """Closed and fully open are places to be too."""
    validated = await SpookTrigger.async_validate_config(
        hass, {"target": {"entity_id": BLINDS}, "options": {"position": position}}
    )

    assert validated["options"]["position"] == int(float(str(position)))


async def test_a_target_is_required(hass: HomeAssistant) -> None:
    """Without a cover or valve, there is nothing to move."""
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(
            hass, {"target": {}, "options": {"position": 30}}
        )


async def test_getting_to_the_position_fires(hass: HomeAssistant) -> None:
    """The point of the whole thing."""
    await _at(hass, 0, state="closed")
    handed, unsub = await _attach(hass)

    await _at(hass, 10, state="opening")
    assert handed == []

    await _at(hass, 30)
    unsub()

    assert len(handed) == 1
    payload, _context = handed[0]
    assert payload["entity_id"] == BLINDS
    assert payload["position"] == 30  # noqa: PLR2004


@pytest.mark.parametrize(
    ("before", "after"), [(20, 40), (40, 20)], ids=["opening past", "closing past"]
)
async def test_moving_past_it_fires(
    hass: HomeAssistant, before: int, after: int
) -> None:
    """A cover moving quickly can skip the very position asked for."""
    await _at(hass, before)
    handed, unsub = await _attach(hass)

    await _at(hass, after)
    unsub()

    assert len(handed) == 1


@pytest.mark.parametrize(("before", "after"), [(30, 30), (30, 40), (10, 20), (50, 40)])
async def test_not_getting_there_does_not_fire(
    hass: HomeAssistant, before: int, after: int
) -> None:
    """Staying there, leaving it, or moving on the wrong side of it."""
    await _at(hass, before)
    handed, unsub = await _attach(hass)

    await _at(hass, after, state="closing")
    unsub()

    assert handed == []


async def test_leaving_and_coming_back_fires_again(hass: HomeAssistant) -> None:
    """Every trip to the position is its own."""
    await _at(hass, 0, state="closed")
    handed, unsub = await _attach(hass)

    await _at(hass, 30)
    await _at(hass, 80)
    await _at(hass, 30)
    unsub()

    assert len(handed) == 2  # noqa: PLR2004


@pytest.mark.parametrize("position", [0, 100], ids=["closed", "fully open"])
async def test_the_ends_can_be_reached(hass: HomeAssistant, position: int) -> None:
    """Closed and fully open are positions like any other."""
    await _at(hass, 50)
    handed, unsub = await _attach(hass, position=position)

    await _at(hass, position, state="closed" if position == 0 else "open")
    unsub()

    assert len(handed) == 1


async def test_coming_back_at_the_position_is_not_reaching_it(
    hass: HomeAssistant,
) -> None:
    """With no position before, there is no movement to judge."""
    await _at(hass, 0, state="closed")
    handed, unsub = await _attach(hass)

    await _at(hass, None, state=STATE_UNAVAILABLE)
    await _at(hass, 30)
    unsub()

    assert handed == []


async def test_a_restored_position_is_no_position(hass: HomeAssistant) -> None:
    """At a start, an entity not set up yet is restored as unavailable.

    That state still carries the position it had before the restart, which
    is a memory, not where the cover is. Coming back from it is not a move.
    """
    await _at(hass, 0, state="closed")
    handed, unsub = await _attach(hass)

    hass.states.async_set(
        BLINDS, STATE_UNAVAILABLE, {"current_position": 10, "restored": True}
    )
    await hass.async_block_till_done()
    await _at(hass, 30)
    unsub()

    assert handed == []


async def test_a_cover_without_positions_never_fires(hass: HomeAssistant) -> None:
    """One that only opens and closes has no position to reach."""
    await _at(hass, None, state="closed")
    handed, unsub = await _attach(hass, position=100)

    await _at(hass, None, state="open")
    unsub()

    assert handed == []


async def test_a_valve_reaches_a_position_too(hass: HomeAssistant) -> None:
    """Half open is a place a valve can be as well."""
    await _at(hass, 0, state="closed", entity_id="valve.garden")
    handed, unsub = await _attach(
        hass, position=50, target={"entity_id": "valve.garden"}
    )

    await _at(hass, 50, entity_id="valve.garden")
    unsub()

    assert len(handed) == 1


async def test_only_covers_and_valves_in_an_area_count(
    hass: HomeAssistant,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """An area holds all sorts, whatever their attributes happen to be called."""
    area = area_registry.async_create("Living room")
    cover = entity_registry.async_get_or_create("cover", "demo", "blinds")
    lookalike = entity_registry.async_get_or_create("sensor", "demo", "lookalike")
    for entry in (cover, lookalike):
        entity_registry.async_update_entity(entry.entity_id, area_id=area.id)
        await _at(hass, 0, entity_id=entry.entity_id)

    handed, unsub = await _attach(hass, target={"area_id": area.id})

    await _at(hass, 30, entity_id=lookalike.entity_id)
    await _at(hass, 30, entity_id=cover.entity_id)
    unsub()

    assert [payload["entity_id"] for payload, _context in handed] == [cover.entity_id]


async def test_it_carries_the_context_of_the_move(hass: HomeAssistant) -> None:
    """Whoever moved it is on it, for Spook's own context conditions."""
    await _at(hass, 0, state="closed")
    handed, unsub = await _attach(hass)

    theirs = Context(user_id="abc123")
    await _at(hass, 30, context=theirs)
    unsub()

    _payload, context = handed[0]
    assert context is theirs
