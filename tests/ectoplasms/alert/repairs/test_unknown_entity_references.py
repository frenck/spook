"""Tests for the alert unknown entity references repair."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import async_fire_time_changed
from homeassistant.core import State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.alert.repairs.unknown_entity_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about, async_count_scheduled_inspections

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er

_YAML_CONFIG = "custom_components.spook.ectoplasms.alert.configuration.async_integration_yaml_config"
_ISSUE_ID = "alert_unknown_entity_references_alert.garage"


@pytest.fixture(name="alert_set_up")
def alert_set_up_fixture(hass: HomeAssistant) -> None:
    """Make Home Assistant look like it has the alert integration loaded."""
    hass.config.components.add("alert")


def _alert_yaml(**alerts: dict) -> dict:
    """Return an alert YAML configuration as Home Assistant validates it."""
    return {"alert": alerts}


@pytest.mark.usefixtures("alert_set_up")
async def test_watched_entity_that_is_gone_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an alert watching a non-existing entity is reported."""
    config = _alert_yaml(
        garage={
            "name": "Garage door",
            "entity_id": "binary_sensor.gone",
            "notifiers": [],
        },
    )

    with patch(_YAML_CONFIG, return_value=config):
        await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["alert"] == "Garage door"
    assert issue.translation_placeholders["entity_id"] == "alert.garage"
    assert "binary_sensor.gone" in issue.translation_placeholders["entities"]


@pytest.mark.usefixtures("alert_set_up")
async def test_watched_entity_in_the_registry_is_not_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an alert watching a registered entity is left alone."""
    entry = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "garage_door", suggested_object_id="garage_door"
    )
    config = _alert_yaml(
        garage={"name": "Garage door", "entity_id": entry.entity_id, "notifiers": []},
    )

    with patch(_YAML_CONFIG, return_value=config):
        await SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


@pytest.mark.usefixtures("alert_set_up")
async def test_watched_state_only_entity_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an alert watching a state-only entity is left alone.

    The false-positive twin. An alert may watch an entity that has no
    registry entry at all, and one in a domain the shared entity filtering
    ignores wholesale. Both exist and neither is broken.
    """
    hass.states.async_set("device_tracker.phone", "not_home")
    hass.states.async_set("group.everyone", "home")
    config = _alert_yaml(
        away={"name": "Away", "entity_id": "device_tracker.phone", "notifiers": []},
        family={"name": "Family", "entity_id": "group.everyone", "notifiers": []},
    )

    with patch(_YAML_CONFIG, return_value=config):
        await SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


async def test_alert_not_set_up_reads_no_configuration(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test nothing is read back when the alert integration is not loaded."""
    with patch(_YAML_CONFIG) as yaml_config:
        await SpookRepair(hass).async_inspect()

    yaml_config.assert_not_called()
    assert not issue_registry.issues


@pytest.mark.usefixtures("alert_set_up")
async def test_configuration_is_read_strictly(hass: HomeAssistant) -> None:
    """Test the configuration is read in a way that fails loudly.

    Without `raise_on_failure`, a configuration that will not validate comes
    back as `None`, which is indistinguishable from having no alerts and
    would make the inspection clear every issue it had raised.
    """
    with patch(_YAML_CONFIG, return_value={}) as yaml_config:
        await SpookRepair(hass).async_inspect()

    yaml_config.assert_called_once_with(hass, "alert", raise_on_failure=True)


@pytest.mark.usefixtures("alert_set_up")
async def test_unreadable_configuration_keeps_existing_issues(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a configuration Spook cannot read does not clear what it found.

    A configuration that will not validate is not the same as a
    configuration without alerts. Home Assistant keeps the alerts it already
    loaded running, so the broken ones are still broken. The inspection has
    to abort rather than report all clear.
    """
    # Found before the restart, and still in the registry.
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{_ISSUE_ID}_0123abcd",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="alert_unknown_entity_references",
    )
    config = _alert_yaml(
        garage={"name": "Garage door", "entity_id": "binary_sensor.gone"},
    )
    repair = SpookRepair(hass)

    with (
        patch(_YAML_CONFIG, side_effect=HomeAssistantError("broken")),
        pytest.raises(HomeAssistantError),
    ):
        await repair._async_inspect_with_cleanup()

    assert async_issue_about(issue_registry, _ISSUE_ID)

    # A read that failed is not remembered: the next look reads again.
    with patch(_YAML_CONFIG, return_value=config) as yaml_config:
        await repair._async_inspect_with_cleanup()

    yaml_config.assert_called_once()
    assert async_issue_about(issue_registry, _ISSUE_ID)


async def _let_time_pass(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, passed: timedelta
) -> None:
    """Move the clock on, and let whatever comes due run."""
    freezer.tick(passed)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("alert_set_up")
async def test_a_configuration_that_could_not_be_read_gets_another_go(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a first read that failed is tried again, without anything happening.

    Nothing about a broken file says when it is fixed, so the daily look is
    what gets the alerts read after all.
    """
    config = _alert_yaml(
        garage={"name": "Garage door", "entity_id": "binary_sensor.gone"},
    )
    repair = SpookRepair(hass)

    with patch(_YAML_CONFIG, side_effect=HomeAssistantError("broken")):
        await repair.async_activate()
        await _let_time_pass(hass, freezer, timedelta(seconds=5))

    assert async_issue_about(issue_registry, _ISSUE_ID) is None

    with patch(_YAML_CONFIG, return_value=config):
        await _let_time_pass(hass, freezer, timedelta(days=1))
        await _let_time_pass(hass, freezer, timedelta(seconds=5))

    assert async_issue_about(issue_registry, _ISSUE_ID)

    await repair.async_deactivate()


@pytest.mark.usefixtures("alert_set_up")
async def test_configuration_is_read_once_per_run(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the configuration is read once, and kept for every look after.

    Home Assistant cannot reload alerts, so what it read at the start is
    what runs until it restarts. Reading the file again on every look took
    seconds on a large configuration, and could only find the same alerts,
    or edits that are not running yet. A file broken since changes nothing
    either: the alerts that run are the ones read.
    """
    config = _alert_yaml(
        garage={"name": "Garage door", "entity_id": "binary_sensor.gone"},
    )
    repair = SpookRepair(hass)

    with patch(_YAML_CONFIG, return_value=config) as yaml_config:
        await repair._async_inspect_with_cleanup()
        await repair._async_inspect_with_cleanup()

    yaml_config.assert_called_once()
    assert async_issue_about(issue_registry, _ISSUE_ID)

    with patch(_YAML_CONFIG, side_effect=HomeAssistantError("broken")):
        await repair._async_inspect_with_cleanup()

    assert async_issue_about(issue_registry, _ISSUE_ID)


@pytest.mark.usefixtures("alert_set_up")
async def test_watched_state_only_entity_going_away_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an alert breaks when the state-only entity it watches disappears.

    A state-only entity leaves no trace in the entity registry, so this
    transition happens without a single registry event.
    """
    hass.states.async_set("device_tracker.phone", "home")
    config = _alert_yaml(
        garage={"name": "Garage door", "entity_id": "device_tracker.phone"},
    )
    repair = SpookRepair(hass)

    with patch(_YAML_CONFIG, return_value=config):
        await repair._async_inspect_with_cleanup()
        assert async_issue_about(issue_registry, _ISSUE_ID) is None

        hass.states.async_remove("device_tracker.phone")
        await repair._async_inspect_with_cleanup()

    assert async_issue_about(issue_registry, _ISSUE_ID)


@pytest.mark.usefixtures("alert_set_up")
async def test_issue_is_cleaned_up_when_the_entity_returns(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue goes away once the watched entity exists again."""
    config = _alert_yaml(
        garage={
            "name": "Garage door",
            "entity_id": "binary_sensor.garage",
            "notifiers": [],
        },
    )
    repair = SpookRepair(hass)

    with patch(_YAML_CONFIG, return_value=config):
        await repair._async_inspect_with_cleanup()
        assert async_issue_about(issue_registry, _ISSUE_ID)

        hass.states.async_set("binary_sensor.garage", "off")
        await repair._async_inspect_with_cleanup()

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def _count_scheduled_inspections(
    hass: HomeAssistant,
    entity_id: str,
    old_state: State | None,
    new_state: State | None,
) -> int:
    """Return how many inspections one state change schedules.

    Runs a real inspection first, because that is what tells the listener
    which entities are worth waking up for.
    """
    config = _alert_yaml(
        garage={"name": "Garage door", "entity_id": "device_tracker.phone"},
    )
    repair = SpookRepair(hass)

    with patch(_YAML_CONFIG, return_value=config):
        await repair.async_activate()
        await repair.async_inspect()

    return await async_count_scheduled_inspections(
        hass, repair, entity_id, old_state, new_state
    )


@pytest.mark.usefixtures("alert_set_up")
async def test_watched_entity_addition_rechecks_alert_repairs(
    hass: HomeAssistant,
) -> None:
    """Test a watched entity appearing schedules an inspection."""
    assert (
        await _count_scheduled_inspections(
            hass,
            "device_tracker.phone",
            None,
            State("device_tracker.phone", "home"),
        )
        == 1
    )


@pytest.mark.usefixtures("alert_set_up")
async def test_watched_entity_removal_rechecks_alert_repairs(
    hass: HomeAssistant,
) -> None:
    """Test a watched entity disappearing schedules an inspection.

    This is the transition an alert breaks on without the entity registry
    ever hearing about it.
    """
    assert (
        await _count_scheduled_inspections(
            hass,
            "device_tracker.phone",
            State("device_tracker.phone", "home"),
            None,
        )
        == 1
    )


@pytest.mark.usefixtures("alert_set_up")
async def test_watched_entity_update_does_not_recheck_alert_repairs(
    hass: HomeAssistant,
) -> None:
    """Test an ordinary state change does not schedule an inspection."""
    assert (
        await _count_scheduled_inspections(
            hass,
            "device_tracker.phone",
            State("device_tracker.phone", "home"),
            State("device_tracker.phone", "not_home"),
        )
        == 0
    )


@pytest.mark.usefixtures("alert_set_up")
async def test_unwatched_entity_does_not_recheck_alert_repairs(
    hass: HomeAssistant,
) -> None:
    """Test an entity no alert watches never schedules an inspection.

    An inspection re-reads the configuration from disk, so entities coming
    and going elsewhere in Home Assistant must not drag it along.
    """
    assert (
        await _count_scheduled_inspections(
            hass,
            "sensor.something_else",
            None,
            State("sensor.something_else", "42"),
        )
        == 0
    )
