"""Tests for what Spook tells System information about itself."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from custom_components.spook import system_health
from custom_components.spook.const import DOMAIN
from custom_components.spook.integration_linking import (
    link_sub_integrations,
    sub_integration_links,
)

if TYPE_CHECKING:
    import pytest

    from homeassistant.core import HomeAssistant


def _create_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Raise an issue, the way any integration does."""
    ir.async_create_issue(
        hass,
        domain,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=issue_id,
    )


async def test_system_health_info(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the info counts Spook's own repairs, and only those."""
    integration = await async_get_integration(hass, DOMAIN)
    monkeypatch.setattr(
        system_health,
        "sub_integration_links",
        lambda _hass: {"one": True, "two": True, "three": True, "four": False},
    )
    _create_issue(hass, DOMAIN, "found_one")
    _create_issue(hass, DOMAIN, "found_two")
    _create_issue(hass, DOMAIN, "ignored_one")
    ir.async_ignore_issue(hass, DOMAIN, "ignored_one", ignore=True)
    _create_issue(hass, "not_spook", "someone_elses")

    info = await system_health.async_system_health_info(hass)

    assert info == {
        "version": str(integration.version),
        "ghosts_found": 2,
        "ghosts_ignored": 1,
        "helpers_linked": "3 of 4",
    }


def test_system_health_registers_with_a_link_to_spook() -> None:
    """Test System information links straight to Spook's page."""
    registered: list[tuple[Any, str]] = []
    registration = SimpleNamespace(
        async_register_info=lambda info, url: registered.append((info, url))
    )

    system_health.async_register(None, registration)  # type: ignore[arg-type]

    assert registered == [
        (
            system_health.async_system_health_info,
            "/config/integrations/integration/spook",
        )
    ]


def test_sub_integration_links(tmp_path: Path) -> None:
    """Test a missing link shows as missing, not just a full set."""
    fake_hass = SimpleNamespace(config=SimpleNamespace(config_dir=tmp_path))
    names = sorted(
        manifest.parent.name
        for manifest in (Path(system_health.__file__).parent / "integrations").glob(
            "*/manifest.json"
        )
    )
    for name in names:
        (tmp_path / "custom_components" / DOMAIN / "integrations" / name).mkdir(
            parents=True
        )

    assert sub_integration_links(fake_hass) == dict.fromkeys(names, False)

    link_sub_integrations(fake_hass)
    (tmp_path / "custom_components" / names[0]).unlink()

    assert sub_integration_links(fake_hass) == {
        name: name != names[0] for name in names
    }
