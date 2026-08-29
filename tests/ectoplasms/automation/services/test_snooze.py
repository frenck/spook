"""Tests for the automation.snooze action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import Context, CoreState
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.automation.services.snooze import SpookService
from custom_components.spook.snoozing import async_setup_snoozing

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

SLEEPER = "automation.sleeper"
OTHER = "automation.other"
AN_HOUR = timedelta(hours=1)

CONFIG = {
    "automation": [
        {
            "id": name,
            "alias": name.title(),
            "triggers": [{"trigger": "state", "entity_id": "input_boolean.x"}],
            "actions": [],
        }
        for name in ("sleeper", "other")
    ]
}


async def _setup(hass: HomeAssistant) -> None:
    """Set up the automations, the register and the action."""
    assert await async_setup_component(hass, "automation", CONFIG)
    await hass.async_block_till_done()

    hass.set_state(CoreState.running)
    await async_setup_snoozing(hass)
    SpookService(hass).async_register()
    await hass.async_block_till_done()


async def test_it_snoozes_the_targeted_automation(hass: HomeAssistant) -> None:
    """The action is what a person or an automation actually calls."""
    await _setup(hass)

    await hass.services.async_call(
        "automation",
        "snooze",
        {"entity_id": SLEEPER, "duration": {"hours": 1}},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "off"
    assert hass.states.get(OTHER).state == "on", "it snoozed something else too"

    hass.data["spook_snoozing"].async_stop()


async def test_it_snoozes_several_at_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Home Assistant expands the target, so a list is a list."""
    await _setup(hass)

    await hass.services.async_call(
        "automation",
        "snooze",
        {"entity_id": [SLEEPER, OTHER], "duration": {"hours": 1}},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "off"
    assert hass.states.get(OTHER).state == "off"

    freezer.tick(AN_HOUR + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on"
    assert hass.states.get(OTHER).state == "on"

    hass.data["spook_snoozing"].async_stop()


async def test_the_caller_travels_with_the_switching_off(
    hass: HomeAssistant,
) -> None:
    """An automation watching this one switch off can still tell who asked.

    Which is the business Spook's own context conditions are in, so the action
    dropping the caller here would be an odd thing for it to do.
    """
    await _setup(hass)

    asked = Context()
    await hass.services.async_call(
        "automation",
        "snooze",
        {"entity_id": SLEEPER, "duration": {"hours": 1}},
        blocking=True,
        context=asked,
    )
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).context.id == asked.id

    hass.data["spook_snoozing"].async_stop()


async def test_a_snooze_of_nothing_is_refused(hass: HomeAssistant) -> None:
    """It would turn an automation off and straight back on, for nothing.

    Anything watching that automation would see the pulse, so this is a
    mistake worth saying out loud rather than carrying out.
    """
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "automation",
            "snooze",
            {"entity_id": SLEEPER, "duration": {"seconds": 0}},
            blocking=True,
        )

    assert hass.states.get(SLEEPER).state == "on"
    assert hass.data["spook_snoozing"].async_until(SLEEPER) is None

    hass.data["spook_snoozing"].async_stop()


async def test_a_duration_past_the_end_of_the_calendar_is_refused(
    hass: HomeAssistant,
) -> None:
    """Time periods run further than datetimes do.

    So a big enough number of days lands past the end of the calendar, and
    that is a validation error rather than an overflow thrown halfway through
    turning an automation off.
    """
    await _setup(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "automation",
            "snooze",
            {"entity_id": SLEEPER, "duration": {"days": 999999999}},
            blocking=True,
        )

    assert hass.states.get(SLEEPER).state == "on"

    hass.data["spook_snoozing"].async_stop()


async def test_a_duration_is_required(hass: HomeAssistant) -> None:
    """Without one there is no snooze, only an off switch."""
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "automation", "snooze", {"entity_id": SLEEPER}, blocking=True
        )

    assert hass.states.get(SLEEPER).state == "on"

    hass.data["spook_snoozing"].async_stop()
