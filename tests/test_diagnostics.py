"""Tests for what Spook puts in a diagnostics download."""

from __future__ import annotations

from typing import TYPE_CHECKING
import json

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.helpers import issue_registry as ir

from custom_components.spook import diagnostics
from custom_components.spook.const import DOMAIN

if TYPE_CHECKING:
    import pytest

    from homeassistant.core import HomeAssistant


def _create_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Raise an issue that names something, the way a real repair does."""
    ir.async_create_issue(
        hass,
        domain,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="automation_unknown_entity_references",
        translation_placeholders={"automation": "Grandma's bedroom lights"},
    )


async def test_diagnostics(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the download holds the links, the helpers and Spook's repairs."""
    monkeypatch.setattr(
        diagnostics,
        "sub_integration_links",
        lambda _hass: {"spook_inverse": False, "spook_calibration": True},
    )
    MockConfigEntry(
        domain="spook_inverse", state=ConfigEntryState.NOT_LOADED
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="spook_inverse",
        disabled_by=ConfigEntryDisabler.USER,
    ).add_to_hass(hass)
    _create_issue(hass, DOMAIN, "found")
    _create_issue(hass, DOMAIN, "ignored")
    ir.async_ignore_issue(hass, DOMAIN, "ignored", ignore=True)
    _create_issue(hass, "not_spook", "someone_elses")
    entry = MockConfigEntry(domain=DOMAIN)

    result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)

    assert result["sub_integrations"] == {
        "spook_inverse": {
            "linked": False,
            "entries": [
                {"state": "not_loaded", "disabled_by": None},
                {"state": "not_loaded", "disabled_by": "user"},
            ],
        },
        "spook_calibration": {"linked": True, "entries": []},
    }
    repairs = {repair["issue_id"]: repair for repair in result["repairs"]}
    assert set(repairs) == {"found", "ignored"}
    assert repairs["found"]["ignored"] is False
    assert repairs["ignored"]["ignored"] is True
    assert repairs["found"]["active"] is True
    assert repairs["found"]["translation_key"] == (
        "automation_unknown_entity_references"
    )
    # People paste this into public issues, so the names stay out.
    assert "Grandma" not in json.dumps(result)
