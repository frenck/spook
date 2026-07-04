"""Tests for the unused blueprints repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.components import blueprint
from homeassistant.components.blueprint import Blueprint
from homeassistant.components.blueprint.errors import FailedToLoad
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs import unused_blueprints
from custom_components.spook.ectoplasms.homeassistant.repairs.unused_blueprints import (
    SpookRepair,
)
from custom_components.spook.repairs import (
    UnusedBlueprintFixFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE_ID = "unused_blueprints_automation:motion.yaml"


@pytest.fixture(autouse=True)
def _aged_blueprints(monkeypatch: pytest.MonkeyPatch) -> None:
    """Treat every blueprint file as old, so the grace period never hides it."""
    monkeypatch.setattr(unused_blueprints, "_file_mtime", lambda _path: 0.0)


class _FakeDomainBlueprints:
    """Minimal stand-in for a core DomainBlueprints."""

    def __init__(self, blueprints: dict[str, Any]) -> None:
        """Store the blueprints to hand out."""
        self._blueprints = blueprints
        self.removed: list[str] = []
        self.blueprint_folder = Path("/nonexistent")

    async def async_get_blueprints(self) -> dict[str, Any]:
        """Return the blueprints."""
        return self._blueprints

    async def async_remove_blueprint(self, path: str) -> None:
        """Record and drop the blueprint."""
        self.removed.append(path)
        self._blueprints.pop(path, None)


def _blueprint(name: str = "Motion light") -> Blueprint:
    """Build a minimal, valid automation blueprint."""
    return Blueprint(
        {"blueprint": {"name": name, "domain": "automation"}},
        expected_domain="automation",
        schema=BLUEPRINT_SCHEMA,
    )


def _install(hass: HomeAssistant, domain: str, blueprints: dict[str, Any]) -> None:
    """Install fake domain blueprints into hass."""
    hass.data[blueprint.DOMAIN] = {domain: _FakeDomainBlueprints(blueprints)}


async def test_unused_blueprint_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a blueprint used by no automation is reported."""
    _install(hass, "automation", {"motion.yaml": _blueprint()})

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.is_fixable
    assert issue.translation_placeholders == {
        "blueprint": "Motion light",
        "domain": "automation",
    }
    assert issue.data == {
        "unused_blueprint_domain": "automation",
        "unused_blueprint_path": "motion.yaml",
        "blueprint": "Motion light",
    }


async def test_recently_added_blueprint_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a blueprint whose file was just added is left alone."""
    # A modification time in the future is comfortably within the grace.
    monkeypatch.setattr(unused_blueprints, "_file_mtime", lambda _path: 9_999_999_999.0)
    _install(hass, "automation", {"motion.yaml": _blueprint()})

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_used_blueprint_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a blueprint with a consumer is left alone."""
    _install(hass, "automation", {"motion.yaml": _blueprint()})
    monkeypatch.setattr(
        unused_blueprints,
        "automations_with_blueprint",
        lambda _hass, path: ["automation.hall"] if path == "motion.yaml" else [],
    )

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_unloadable_blueprint_is_ignored(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a blueprint that failed to load is not reported."""
    err = FailedToLoad("automation", "motion.yaml", FileNotFoundError())
    _install(hass, "automation", {"motion.yaml": err})

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_blueprint_in_uncheckable_domain_is_ignored(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a blueprint in a domain Spook cannot check is left alone."""
    _install(hass, "template", {"motion.yaml": _blueprint()})

    await SpookRepair(hass).async_inspect()

    assert (
        issue_registry.async_get_issue(DOMAIN, "unused_blueprints_template:motion.yaml")
        is None
    )


async def test_fix_flow_remove_option_removes_blueprint(
    hass: HomeAssistant,
) -> None:
    """Test the remove menu option deletes the blueprint file."""
    _install(hass, "automation", {"motion.yaml": _blueprint()})
    fake = hass.data[blueprint.DOMAIN]["automation"]

    flow = await async_create_fix_flow(
        hass,
        _ISSUE_ID,
        {
            "unused_blueprint_domain": "automation",
            "unused_blueprint_path": "motion.yaml",
            "blueprint": "Motion light",
        },
    )
    assert isinstance(flow, UnusedBlueprintFixFlow)
    flow.hass = hass
    flow.data = {
        "unused_blueprint_domain": "automation",
        "unused_blueprint_path": "motion.yaml",
        "blueprint": "Motion light",
    }

    menu = await flow.async_step_init()
    assert menu["type"] == FlowResultType.MENU
    # The menu names both the blueprint and its domain.
    assert menu["description_placeholders"] == {
        "blueprint": "Motion light",
        "domain": "automation",
    }

    result = await flow.async_step_remove()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert fake.removed == ["motion.yaml"]


async def test_fix_flow_ignore_option_dismisses_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the keep menu option ignores the issue and keeps the blueprint."""
    _install(hass, "automation", {"motion.yaml": _blueprint()})
    await SpookRepair(hass).async_inspect()
    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)

    flow = UnusedBlueprintFixFlow()
    flow.hass = hass
    flow.issue_id = _ISSUE_ID
    flow.data = {
        "unused_blueprint_domain": "automation",
        "unused_blueprint_path": "motion.yaml",
        "blueprint": "Motion light",
    }
    result = await flow.async_step_ignore()

    assert result["type"] == FlowResultType.ABORT
    fake = hass.data[blueprint.DOMAIN]["automation"]
    assert fake.removed == []
    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue is not None
    assert issue.dismissed_version is not None
