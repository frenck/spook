"""Tests for the registry repairs looking once their grace period is over."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from typing import TYPE_CHECKING

from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.helpers import (
    area_registry as ar,
    floor_registry as fr,
    issue_registry as ir,
    label_registry as lr,
)

from custom_components.spook.const import DOMAIN

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant


def _new_area(hass: HomeAssistant) -> str:
    """Create an area, and return its ID."""
    return ar.async_get(hass).async_create("Ghost Room").id


def _new_floor(hass: HomeAssistant) -> str:
    """Create a floor, and return its ID."""
    return fr.async_get(hass).async_create("Attic").floor_id


def _new_label(hass: HomeAssistant) -> str:
    """Create a label, and return its ID."""
    return lr.async_get(hass).async_create("Holiday").label_id


async def _let_time_pass(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, passed: timedelta
) -> None:
    """Move the clock on, and let whatever comes due run."""
    freezer.tick(passed)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("repair", "create"),
    [
        ("empty_areas", _new_area),
        ("empty_floors", _new_floor),
        ("unused_labels", _new_label),
    ],
)
async def test_reported_once_the_grace_period_is_over(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    repair: str,
    create: Callable[[HomeAssistant], str],
) -> None:
    """Test one left alone for being new is reported later, without a nudge.

    It is left alone for its first day, and nothing that happens to it says
    when that day is over. Without a look of its own, it waited for some
    other change to come along.
    """
    thing_id = create(hass)
    module = import_module(
        f"custom_components.spook.ectoplasms.homeassistant.repairs.{repair}"
    )
    spook_repair = module.SpookRepair(hass)
    await spook_repair.async_activate()
    await _let_time_pass(hass, freezer, timedelta(seconds=5))

    issue_registry = ir.async_get(hass)
    issue_id = f"{repair}_{thing_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    # Two days on, with nothing happening in between.
    for _ in range(2):
        await _let_time_pass(hass, freezer, timedelta(days=1))
        await _let_time_pass(hass, freezer, timedelta(seconds=5))

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await spook_repair.async_deactivate()
