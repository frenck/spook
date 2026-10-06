"""Tests for enabling and disabling integration entries by domain."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
)

from custom_components.spook.ectoplasms.homeassistant.services import (
    disable_config_entry,
    enable_config_entry,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _async_setup_entry(_hass: HomeAssistant, _entry: MockConfigEntry) -> bool:
    """Set up nothing, successfully."""
    return True


async def _async_unload_entry(_hass: HomeAssistant, _entry: MockConfigEntry) -> bool:
    """Unload nothing, successfully."""
    return True


@pytest.fixture(name="entries")
async def entries_fixture(hass: HomeAssistant) -> dict[str, MockConfigEntry]:
    """Give two integrations some entries, and register both actions."""
    # The actions belong to Home Assistant's own integration, and only
    # register once that is set up.
    assert await async_setup_component(hass, "homeassistant", {})
    for domain in ("bulbs", "plugs"):
        mock_integration(
            hass,
            MockModule(
                domain,
                async_setup_entry=_async_setup_entry,
                async_unload_entry=_async_unload_entry,
            ),
        )

    made = {
        name: MockConfigEntry(domain=domain, title=name)
        for name, domain in (
            ("kitchen", "bulbs"),
            ("attic", "bulbs"),
            ("desk", "plugs"),
        )
    }
    for entry in made.values():
        entry.add_to_hass(hass)

    disable_config_entry.SpookService(hass).async_register()
    enable_config_entry.SpookService(hass).async_register()
    return made


def _disabled(hass: HomeAssistant) -> set[str]:
    """Return the titles of the entries that are disabled."""
    return {
        entry.title
        for entry in hass.config_entries.async_entries()
        if entry.disabled_by is ConfigEntryDisabler.USER
    }


@pytest.mark.usefixtures("entries")
async def test_a_domain_takes_every_entry_of_it(hass: HomeAssistant) -> None:
    """Every entry of the integration, and nothing of another one."""
    await hass.services.async_call(
        "homeassistant", "disable_config_entry", {"domain": "bulbs"}, blocking=True
    )
    assert _disabled(hass) == {"kitchen", "attic"}

    await hass.services.async_call(
        "homeassistant", "enable_config_entry", {"domain": ["bulbs"]}, blocking=True
    )
    assert _disabled(hass) == set()


async def test_domains_and_entries_add_up(
    hass: HomeAssistant, entries: dict[str, MockConfigEntry]
) -> None:
    """Named both ways, all of them count, and nothing twice."""
    await hass.services.async_call(
        "homeassistant",
        "disable_config_entry",
        {
            "domain": "plugs",
            "config_entry_id": [entries["kitchen"].entry_id, entries["desk"].entry_id],
        },
        blocking=True,
    )

    assert _disabled(hass) == {"kitchen", "desk"}


async def test_an_entry_id_on_its_own_still_works(
    hass: HomeAssistant, entries: dict[str, MockConfigEntry]
) -> None:
    """The action did this before, and still does."""
    await hass.services.async_call(
        "homeassistant",
        "disable_config_entry",
        {"config_entry_id": entries["attic"].entry_id},
        blocking=True,
    )

    assert _disabled(hass) == {"attic"}


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("action", ["disable_config_entry", "enable_config_entry"])
async def test_a_domain_without_entries_is_refused(
    hass: HomeAssistant, action: str
) -> None:
    """A typo would otherwise do nothing, and say nothing about it."""
    with pytest.raises(ServiceValidationError, match="bulsb integration has no"):
        await hass.services.async_call(
            "homeassistant", action, {"domain": ["bulbs", "bulsb"]}, blocking=True
        )

    # Refused before anything changed, the right half included.
    assert _disabled(hass) == set()


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("action", ["disable_config_entry", "enable_config_entry"])
async def test_asking_for_nothing_is_refused(hass: HomeAssistant, action: str) -> None:
    """Neither an entry nor an integration: there is nothing to change."""
    with pytest.raises(ServiceValidationError, match="Name the integration entries"):
        await hass.services.async_call("homeassistant", action, {}, blocking=True)
