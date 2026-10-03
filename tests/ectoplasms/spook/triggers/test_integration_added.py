"""Tests for the spook.integration_added trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryState,
)
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
    mock_platform,
)

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_DOMAIN = "new_kid"


def _integration(hass: HomeAssistant) -> None:
    """Provide an integration whose entries set up and unload fine."""
    mock_integration(
        hass,
        MockModule(
            _DOMAIN,
            async_setup_entry=AsyncMock(return_value=True),
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    mock_platform(hass, f"{_DOMAIN}.config_flow", None)


async def _automation(hass: HomeAssistant) -> list[dict]:
    """Set up an automation on the trigger and record every run."""
    ran: list[dict] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(dict(call.data))

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "new integration",
                    "trigger": {"platform": "spook.integration_added"},
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "entry_id": "{{ trigger.entry_id }}",
                                "domain": "{{ trigger.domain }}",
                                "title": "{{ trigger.title }}",
                                "source": "{{ trigger.source }}",
                            },
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def _add(hass: HomeAssistant, source: str) -> MockConfigEntry:
    """Add an entry the way Home Assistant does at the end of a flow."""
    _integration(hass)
    entry = MockConfigEntry(domain=_DOMAIN, title="New kid", source=source)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    return entry


async def test_an_added_integration_is_reported(hass: HomeAssistant) -> None:
    """Test an integration added fires the trigger, with what and how."""
    ran = await _automation(hass)

    entry = await _add(hass, SOURCE_ZEROCONF)

    assert ran == [
        {
            "entry_id": entry.entry_id,
            "domain": _DOMAIN,
            "title": "New kid",
            "source": SOURCE_ZEROCONF,
        }
    ]


async def test_an_ignored_discovery_is_not_an_integration(
    hass: HomeAssistant,
) -> None:
    """Test ignoring a discovered device does not fire.

    It is stored as an entry so the discovery is not offered again, and
    nothing is set up by it.
    """
    ran = await _automation(hass)

    await _add(hass, SOURCE_IGNORE)

    assert ran == []


async def test_entries_already_there_stay_quiet(hass: HomeAssistant) -> None:
    """Test entries present before the automation, a restart's, do not fire.

    Changes to them, a reload for one, are not additions either.
    """
    entry = MockConfigEntry(domain=_DOMAIN, title="Old hand", source=SOURCE_USER)
    entry.add_to_hass(hass)
    ran = await _automation(hass)

    # Setting up and unloading again, the way a reload goes, tells every
    # listener about each step. None of those is the entry being added.
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)
    await hass.async_block_till_done()

    assert ran == []
