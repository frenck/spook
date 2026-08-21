"""Tests for the alert unknown entity references repair."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.alert.repairs.unknown_entity_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er, issue_registry as ir

_YAML_CONFIG = "custom_components.spook.ectoplasms.alert.configuration.async_integration_yaml_config"


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

    issue = issue_registry.async_get_issue(
        DOMAIN, "alert_unknown_entity_references_alert.garage"
    )
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
async def test_unreadable_configuration_is_survived(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a configuration that will not validate does not raise."""
    with patch(_YAML_CONFIG, return_value=None):
        await SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


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
        assert issue_registry.async_get_issue(
            DOMAIN, "alert_unknown_entity_references_alert.garage"
        )

        hass.states.async_set("binary_sensor.garage", "off")
        await repair._async_inspect_with_cleanup()

    assert not issue_registry.async_get_issue(
        DOMAIN, "alert_unknown_entity_references_alert.garage"
    )
