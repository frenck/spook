"""Tests for the Spook cooldown condition."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components import script
from homeassistant.helpers.condition import ConditionConfig
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import voluptuous as vol

from custom_components.spook.condition import async_get_conditions
from custom_components.spook.ectoplasms.spook.conditions.cooldown import SpookCondition
import pytest

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

_DURATION = timedelta(minutes=5)


def _condition(hass: HomeAssistant) -> SpookCondition:
    """Build a cooldown condition with a five minute duration."""
    return SpookCondition(hass, ConditionConfig(options={"duration": _DURATION}))


def _variables(last_triggered: datetime | None) -> dict:
    """Build the automation `this` variables with a last-triggered time."""
    return {"this": {"attributes": {"last_triggered": last_triggered}}}


async def test_condition_is_discovered(hass: HomeAssistant) -> None:
    """Test the cooldown condition is discovered as spook.cooldown."""
    conditions = await async_get_conditions(hass)
    assert conditions["cooldown"] is SpookCondition


async def test_config_validation(hass: HomeAssistant) -> None:
    """Test the condition validates its duration option."""
    valid = await SpookCondition.async_validate_config(
        hass, {"options": {"duration": "00:05:00"}}
    )
    assert valid["options"]["duration"] == _DURATION

    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(hass, {"options": {}})


async def _check(hass: HomeAssistant, variables: dict | None) -> bool | None:
    """Set up a cooldown condition and check it once."""
    condition = _condition(hass)
    await condition.async_setup()

    return condition.async_check(variables=variables)


async def test_recent_run_blocks(hass: HomeAssistant) -> None:
    """Test a run within the cooldown fails the condition."""
    recent = dt_util.utcnow() - timedelta(minutes=1)

    assert await _check(hass, _variables(recent)) is False


async def test_elapsed_run_passes(hass: HomeAssistant) -> None:
    """Test a run older than the cooldown passes the condition."""
    old = dt_util.utcnow() - timedelta(minutes=10)

    assert await _check(hass, _variables(old)) is True


async def test_exactly_at_the_boundary_passes(hass: HomeAssistant) -> None:
    """Test a run exactly one cooldown ago passes."""
    boundary = dt_util.utcnow() - _DURATION

    assert await _check(hass, _variables(boundary)) is True


async def test_never_run_passes(hass: HomeAssistant) -> None:
    """Test the condition passes when there is no last-run info."""
    assert await _check(hass, _variables(None)) is True
    assert await _check(hass, {}) is True
    assert await _check(hass, None) is True
    assert await _check(hass, {"this": {}}) is True


async def test_this_is_snapshotted_before_the_run(hass: HomeAssistant) -> None:
    """Test `this` still holds the previous run when the sequence executes.

    The whole condition rests on this: Home Assistant builds `this` from the
    entity state before starting the run, while `last_triggered` is bumped as
    the run begins. If that order ever flips, a run would see its own
    timestamp, the cooldown would never elapse, and every unit test above
    would still pass. So assert the contract rather than trust it.
    """
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            "script": {
                "probe": {
                    "sequence": [
                        {
                            "event": "cooldown_probe",
                            "event_data": {
                                "seen": "{{ this.attributes.last_triggered }}",
                            },
                        },
                    ],
                },
            },
        },
    )
    await hass.async_block_till_done()

    seen: list[object] = []
    hass.bus.async_listen(
        "cooldown_probe", lambda event: seen.append(event.data["seen"])
    )

    await hass.services.async_call(script.DOMAIN, "probe", blocking=True)
    await hass.async_block_till_done()
    await hass.services.async_call(script.DOMAIN, "probe", blocking=True)
    await hass.async_block_till_done()

    # A first ever run has nothing to compare against, so the cooldown is
    # satisfied. A second run sees the first, which is what makes it a
    # throttle instead of a permanent block.
    assert seen[0] is None
    assert seen[1] is not None
