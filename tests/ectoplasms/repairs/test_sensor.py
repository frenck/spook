"""Tests for the repairs issue count sensors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorEntity
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.loader import async_get_integration

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.repairs.sensor import (
    SENSORS,
    HomeAssistantSpookSensorEntity,
)
from tests.repair_helpers import async_add_config_entry, async_disable_config_entry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
async def _sensors(hass: HomeAssistant) -> AsyncIterator[None]:
    """Add the three issue count sensors to Home Assistant."""
    # Their device carries Spook's version, read off the loaded integration.
    await async_get_integration(hass, DOMAIN)

    component = EntityComponent[SensorEntity](
        logging.getLogger(__name__), SENSOR_DOMAIN, hass
    )
    await component.async_add_entities(
        HomeAssistantSpookSensorEntity(description) for description in SENSORS
    )
    yield

    # Taking them out again stops the polling they come with.
    for description in SENSORS:
        await component.async_remove_entity(str(description.entity_id))


def _raise(
    hass: HomeAssistant,
    issue_id: str,
    config_entry_id: str | None = None,
) -> None:
    """Report a repair issue, the way an integration would."""
    ir.async_create_issue(
        hass,
        "hue",
        issue_id,
        config_entry_id=config_entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=issue_id,
    )


def _counts(hass: HomeAssistant) -> tuple[str, str, str]:
    """Return what the total, active and ignored sensors say."""
    return (
        hass.states.get("sensor.issues").state,
        hass.states.get("sensor.active_issues").state,
        hass.states.get("sensor.ignored_issues").state,
    )


async def test_the_issues_of_a_disabled_entry_are_not_counted(
    hass: HomeAssistant,
) -> None:
    """Counted the way the Repairs dashboard shows them.

    Home Assistant hides the issues of a disabled config entry, and shows
    them again once the entry is enabled. Neither raises nor removes an
    issue, and the counts still have to follow.
    """
    entry = async_add_config_entry(hass, "hue")
    _raise(hass, "bridge_gone")
    _raise(hass, "light_gone", entry.entry_id)
    _raise(hass, "sensor_gone", entry.entry_id)
    ir.async_ignore_issue(hass, "hue", "sensor_gone", ignore=True)
    await hass.async_block_till_done()
    assert _counts(hass) == ("3", "2", "1")

    await async_disable_config_entry(hass, entry)
    assert _counts(hass) == ("1", "1", "0"), "counted issues nobody can see"

    await async_disable_config_entry(hass, entry, disabled=False)
    assert _counts(hass) == ("3", "2", "1"), "lost the issues of an enabled entry"
