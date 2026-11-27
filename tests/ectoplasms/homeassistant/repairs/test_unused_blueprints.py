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
from homeassistant.setup import async_setup_component
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
from tests.repair_helpers import wire_fix_flow

from tests.repair_helpers import (
    async_reload_slower_than_the_repair_waits,
    async_wait_out_the_repair,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

    from custom_components.spook.repairs import AbstractSpookRepair

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

    flow = wire_fix_flow(hass, UnusedBlueprintFixFlow(), _ISSUE_ID)
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


# One blueprint of each domain that uses them, and a configuration holding
# one automation or script, on that blueprint or on nothing of the kind.
# What the blueprint holds differs from the one on nothing: a reload leaves
# alone what it reads back as it was, blueprint or not.
_BLUEPRINT_FILES = {
    "automation": """
blueprint:
  name: Spooky
  domain: automation
triggers:
  - trigger: event
    event_type: blueprinted
actions: []
""",
    "script": """
blueprint:
  name: Spooky
  domain: script
sequence:
  - delay: 1
""",
}
_ON_THE_BLUEPRINT = {"use_blueprint": {"path": "frenck/spooky.yaml", "input": {}}}
_CONFIGURATIONS = {
    "automation": (
        {
            "automation": [
                {
                    "id": "lights",
                    "alias": "Lights",
                    "triggers": [{"trigger": "event", "event_type": "spook"}],
                    "actions": [],
                }
            ]
        },
        {"automation": [{"id": "lights", "alias": "Lights", **_ON_THE_BLUEPRINT}]},
    ),
    "script": (
        {"script": {"lights": {"sequence": []}}},
        {"script": {"lights": _ON_THE_BLUEPRINT}},
    ),
}


async def _set_up_on_a_blueprint_or_not(
    hass: HomeAssistant, tmp_path: Path, configuration: dict[str, Any]
) -> AbstractSpookRepair:
    """Set up the Spooky blueprint and a configuration, and the repair on them.

    In a config dir of its own, so the test writes no blueprint anywhere else.
    """
    (domain,) = configuration
    hass.config.config_dir = str(tmp_path)
    path = tmp_path / "blueprints" / domain / "frenck" / "spooky.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(_BLUEPRINT_FILES[domain], encoding="utf-8")

    assert await async_setup_component(hass, domain, configuration)
    await hass.async_block_till_done()
    repair = SpookRepair(hass)
    await repair.async_activate()
    return repair


@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_a_reload_that_starts_using_it_takes_the_issue_away(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    tmp_path: Path,
    domain: str,
) -> None:
    """Test an edited automation or script, once reloaded on it, clears the issue.

    The look the reload call brought came while the YAML was still being
    read, and nothing brought one once the reload was done. The issue stayed
    up, with a button to remove a blueprint that is now used, for a day.
    """
    issue = (DOMAIN, f"unused_blueprints_{domain}:frenck/spooky.yaml")
    without, on_it = _CONFIGURATIONS[domain]
    repair = await _set_up_on_a_blueprint_or_not(hass, tmp_path, without)
    await async_wait_out_the_repair(hass, freezer)
    assert issue in issue_registry.issues

    await async_reload_slower_than_the_repair_waits(hass, freezer, on_it)
    await repair.async_deactivate()

    assert issue not in issue_registry.issues


@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_a_reload_that_stops_using_it_raises_the_issue(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    tmp_path: Path,
    domain: str,
) -> None:
    """Test a reload taking the last use away reports the blueprint unused."""
    issue = (DOMAIN, f"unused_blueprints_{domain}:frenck/spooky.yaml")
    without, on_it = _CONFIGURATIONS[domain]
    repair = await _set_up_on_a_blueprint_or_not(hass, tmp_path, on_it)
    await async_wait_out_the_repair(hass, freezer)
    assert issue not in issue_registry.issues

    await async_reload_slower_than_the_repair_waits(hass, freezer, without)
    await repair.async_deactivate()

    assert issue in issue_registry.issues
