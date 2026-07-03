"""End-to-end test for Spook's repair machinery.

Sets up the Spook config entry with the real repair manager, lets the
inspection debouncers fire through simulated time, and asserts an issue
for an automation with dangling references lands in the real issue
registry.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.setup import async_setup_component

from custom_components import spook
from custom_components.spook.const import DOMAIN
import pytest

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

pytestmark = pytest.mark.usefixtures("skip_dependency_setup")


class _NoopSpookServiceManager:
    """No-op service manager.

    Spook's services register against entity platforms of integrations
    that are not loaded in this test environment.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the no-op service manager."""
        self.hass = hass

    async def async_setup(self) -> None:
        """Set up no services."""

    def async_on_unload(self) -> None:
        """Unload no services."""


async def test_automation_with_dangling_references_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the full path from automation config to a repairs issue."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "spooky_test",
                    "alias": "Spooky Test",
                    "triggers": [
                        {"trigger": "state", "entity_id": "binary_sensor.ghost"},
                    ],
                    "actions": [
                        {
                            "action": "light.turn_on",
                            "target": {"entity_id": "light.ghost"},
                        },
                    ],
                },
            ],
        },
    )

    async def _async_forward_no_ectoplasms(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
    ) -> None:
        """Skip ectoplasm setup; this test targets the repair manager."""

    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", lambda _: False)
    monkeypatch.setattr(
        spook, "async_forward_setup_entry", _async_forward_no_ectoplasms
    )
    monkeypatch.setattr(spook, "SpookServiceManager", _NoopSpookServiceManager)

    # The Lovelace repair requires the Lovelace data container during
    # activation; provide an empty one instead of setting up the frontend.
    hass.data["lovelace"] = SimpleNamespace(dashboards={})

    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Repairs are set up once Home Assistant signals it has started.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    # Let the inspection debouncers (3 second cooldown) fire.
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        "automation_unknown_entity_references_automation.spooky_test",
    )
    assert issue
    assert issue.translation_placeholders
    entities = issue.translation_placeholders["entities"]
    assert "binary_sensor.ghost" in entities
    assert "light.ghost" in entities

    # The dangling action also surfaces as an unknown service reference.
    assert issue_registry.async_get_issue(
        DOMAIN,
        "automation_unknown_service_references_automation.spooky_test",
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
