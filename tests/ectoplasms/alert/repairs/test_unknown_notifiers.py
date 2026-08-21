"""Tests for the alert unknown notifiers repair."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.alert.repairs.unknown_notifiers import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_YAML_CONFIG = "custom_components.spook.ectoplasms.alert.configuration.async_integration_yaml_config"
_ISSUE_ID = "alert_unknown_notifiers_alert.garage"


@pytest.fixture(name="alert_set_up")
def alert_set_up_fixture(hass: HomeAssistant) -> None:
    """Make Home Assistant look like it has the alert integration loaded."""
    hass.config.components.add("alert")


def _alert_yaml(**alerts: dict) -> dict:
    """Return an alert YAML configuration as Home Assistant validates it."""
    return {"alert": alerts}


@pytest.mark.usefixtures("alert_set_up")
async def test_notifier_that_is_gone_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an alert notifying through a non-existing action is reported."""
    hass.services.async_register("notify", "still_here", lambda _call: None)
    config = _alert_yaml(
        garage={
            "name": "Garage door",
            "entity_id": "binary_sensor.garage",
            "notifiers": ["still_here", "old_phone"],
        },
    )

    with patch(_YAML_CONFIG, return_value=config):
        await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["alert"] == "Garage door"
    assert issue.translation_placeholders["entity_id"] == "alert.garage"

    # Only the missing one, and named as the action it would have called.
    assert issue.translation_placeholders["notifiers"] == "- `notify.old_phone`"


@pytest.mark.usefixtures("alert_set_up")
async def test_existing_notifiers_are_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an alert whose notifiers all exist is left alone."""
    hass.services.async_register("notify", "phone", lambda _call: None)
    hass.services.async_register("notify", "persistent_notification", lambda _c: None)
    config = _alert_yaml(
        garage={
            "name": "Garage door",
            "entity_id": "binary_sensor.garage",
            "notifiers": ["phone", "persistent_notification"],
        },
    )

    with patch(_YAML_CONFIG, return_value=config):
        await SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


@pytest.mark.usefixtures("alert_set_up")
async def test_alert_without_notifiers_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an alert that notifies nobody is left alone.

    The false-positive twin. `notifiers:` is optional and defaults to empty,
    which is a legitimate way to run an alert: the entity still tracks the
    state and a dashboard or automation can pick it up from there. An empty
    list is not a broken list.
    """
    config = _alert_yaml(
        garage={
            "name": "Garage door",
            "entity_id": "binary_sensor.garage",
            "notifiers": [],
        },
        attic={"name": "Attic", "entity_id": "binary_sensor.attic"},
    )

    with patch(_YAML_CONFIG, return_value=config):
        await SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


@pytest.mark.usefixtures("alert_set_up")
async def test_notifier_named_like_an_entity_is_still_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a notifier is checked as an action, never as an entity.

    A notifier is a bare action slug. Registering an entity by that name
    changes nothing: the alert calls `notify.<slug>` and that action is what
    has to exist.
    """
    hass.states.async_set("notify.old_phone", "unknown")
    config = _alert_yaml(
        garage={
            "name": "Garage door",
            "entity_id": "binary_sensor.garage",
            "notifiers": ["old_phone"],
        },
    )

    with patch(_YAML_CONFIG, return_value=config):
        await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)


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
async def test_issue_is_cleaned_up_when_the_notifier_returns(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue goes away once the notify action is registered again."""
    config = _alert_yaml(
        garage={
            "name": "Garage door",
            "entity_id": "binary_sensor.garage",
            "notifiers": ["late_phone"],
        },
    )
    repair = SpookRepair(hass)

    with patch(_YAML_CONFIG, return_value=config):
        await repair._async_inspect_with_cleanup()
        assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)

        hass.services.async_register("notify", "late_phone", lambda _call: None)
        await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None
