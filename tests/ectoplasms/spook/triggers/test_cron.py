"""Tests for the spook.cron trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.cron import SpookTrigger
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant


async def _detach(hass: HomeAssistant) -> None:
    """Turn the automation off, which detaches its trigger.

    Home Assistant's test harness fails a test that leaves a timer behind, so
    this doubles as a check that the trigger cleans up after itself.
    """
    await hass.services.async_call(
        "automation",
        "turn_off",
        {"entity_id": "automation.on_a_schedule"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def _automation(hass: HomeAssistant, schedule: str) -> list[str]:
    """Set up an automation on a cron schedule and report each time it runs."""
    ran: list[str] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["at"])

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "on a schedule",
                    "trigger": {
                        "platform": "spook.cron",
                        "options": {"schedule": schedule},
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {"at": "{{ trigger.now }}"},
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key.

    Plain, because Home Assistant prefixes it with the providing integration
    itself: this is `spook.cron` by the time anybody writes it in YAML.
    """
    assert "cron" in await async_get_triggers(hass)


async def test_a_nonsense_expression_is_refused(hass: HomeAssistant) -> None:
    """A bad expression is rejected at validation, naming what is wrong.

    Better here than at three in the morning when the automation was supposed
    to run.
    """
    with pytest.raises(vol.Invalid, match="Invalid crontab expression"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"schedule": "not a schedule"}}
        )


async def test_nicknames_are_refused(hass: HomeAssistant) -> None:
    """`@daily` and friends are not crontab as cronsim reads it.

    Worth pinning: it is the first thing somebody used to cron will try, and
    the documentation says so because of this.
    """
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"schedule": "@daily"}}
        )


async def test_a_valid_expression_is_accepted(hass: HomeAssistant) -> None:
    """The forms the documentation advertises all validate."""
    for schedule in ("*/5 * * * *", "0 7 * * 1-5", "0 12 * * MON#2", "0 3 L * *"):
        assert await SpookTrigger.async_validate_config(
            hass, {"options": {"schedule": schedule}}
        ) == {"options": {"schedule": schedule}}


async def test_it_fires_when_the_schedule_comes_round(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The automation runs at the scheduled minute, and not before."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 11:58:00")))
    ran = await _automation(hass, "0 * * * *")

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not ran

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(ran) == 1

    await _detach(hass)


async def test_it_keeps_firing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Each run lines up the one after it, rather than firing once and stopping."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 11:59:30")))
    ran = await _automation(hass, "*/1 * * * *")

    minutes = 3
    for _ in range(minutes):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert len(ran) == minutes

    await _detach(hass)


async def test_an_impossible_date_is_refused(hass: HomeAssistant) -> None:
    """A date that can never happen is rejected rather than silently never firing.

    cronsim catches the 30th of February at parse time, which is the better
    of the two behaviours: the automation fails to load and says why, instead
    of loading and waiting forever.
    """
    with pytest.raises(vol.Invalid, match="Invalid crontab expression"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"schedule": "0 0 30 2 *"}}
        )


async def test_a_date_years_away_is_fine(hass: HomeAssistant) -> None:
    """The 29th of February resolves to the next leap year, not to nothing."""
    trigger = SpookTrigger(hass, _config("0 0 29 2 *"))
    # pylint: disable-next=protected-access
    upcoming = trigger._next(dt_util.parse_datetime("2026-08-27 12:00:00"))  # noqa: SLF001

    assert upcoming is not None
    assert (upcoming.year, upcoming.month, upcoming.day) == (2028, 2, 29)


def _config(schedule: str) -> TriggerConfig:
    """Build a trigger config, the way core hands one over."""
    return TriggerConfig(key="spook.cron", options={"schedule": schedule})
