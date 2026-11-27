"""Tests for what Spook puts in a diagnostics download."""
# ruff: noqa: SLF001
# pylint: disable=protected-access

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
import json

from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from custom_components.spook import diagnostics
from custom_components.spook.const import DOMAIN
from custom_components.spook.repairs import (
    AbstractSpookRepair,
    LastLook,
    LookOutcome,
    RepairModuleState,
    SpookRepairManager,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
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
    # Some repairs carry a path or URL somebody chose in their ID.
    _create_issue(hass, DOMAIN, "found_/local/grandma-lights-card.js")
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
    assert sorted(
        (repair["active"], repair["ignored"]) for repair in result["repairs"]
    ) == [(True, False), (True, True)]
    assert all(
        repair["translation_key"] == "automation_unknown_entity_references"
        for repair in result["repairs"]
    )
    # People paste this into public issues, so names, paths and URLs stay out,
    # whether a repair carries them in its placeholders or in its ID.
    dumped = json.dumps(result)
    assert "Grandma" not in dumped
    assert "grandma" not in dumped


class _LookingRepair(AbstractSpookRepair):
    """A repair the test says how its last look went."""

    domain = "mock"

    def __init__(self, hass: HomeAssistant, repair: str) -> None:
        """Initialize the repair, under this name."""
        super().__init__(hass)
        self.repair = repair

    async def async_inspect(self) -> None:
        """Inspect nothing."""


async def test_how_the_repairs_did(hass: HomeAssistant) -> None:
    """Test the download says how setting up the repairs went, and each look.

    A failure is told by the type of its error alone: its message can name
    an entity or a path, and people paste this into public issues.
    """
    manager = SpookRepairManager(hass)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.runtime_data = manager

    # Home Assistant is still starting, so nothing is set up yet.
    result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)
    assert result["repair_setup"] == {
        "state": "waiting_for_home_assistant_to_start",
        "modules": {},
        "last_looks": {},
    }

    finished = dt_util.utcnow()
    looks = {
        "fine": LastLook(finished, LookOutcome.FINE),
        "failed": LastLook(finished, LookOutcome.FAILED, "KeyError"),
        "could_not_look": LastLook(
            finished, LookOutcome.COULD_NOT_LOOK, "The icons could not be read"
        ),
        "not_looked_yet": None,
    }
    for name, look in looks.items():
        repair = _LookingRepair(hass, name)
        repair.last_look = look
        manager._repairs.add(repair)
    manager.module_states.update(
        {
            "custom_components.spook.ectoplasms.mock.repairs.fine": (
                RepairModuleState.SET_UP
            ),
            "custom_components.spook.ectoplasms.mock.repairs.broken": (
                RepairModuleState.FAILED_TO_LOAD
            ),
            "custom_components.spook.ectoplasms.mock.repairs.haunted": (
                RepairModuleState.FAILED_TO_SET_UP
            ),
        }
    )
    manager.set_up = True

    result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)

    assert result["repair_setup"] == {
        "state": "set_up",
        "modules": {
            "custom_components.spook.ectoplasms.mock.repairs.broken": "failed_to_load",
            "custom_components.spook.ectoplasms.mock.repairs.fine": "set_up",
            "custom_components.spook.ectoplasms.mock.repairs.haunted": (
                "failed_to_set_up"
            ),
        },
        "last_looks": {
            "mock.could_not_look": {
                "finished": finished.isoformat(),
                "outcome": "could_not_look",
                "reason": "The icons could not be read",
            },
            "mock.failed": {
                "finished": finished.isoformat(),
                "outcome": "failed",
                "error": "KeyError",
            },
            "mock.fine": {"finished": finished.isoformat(), "outcome": "fine"},
            "mock.not_looked_yet": None,
        },
    }


async def test_a_failure_is_told_by_its_type_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the message of an error a look failed on stays out of the download.

    The look really fails, the way it does in the house, with a message that
    names something a person chose.
    """

    class _FailingRepair(_LookingRepair):
        async def async_inspect(self) -> None:
            msg = "light.grandmas_bedroom is not in /config/grandma.yaml"
            raise KeyError(msg)

    manager = SpookRepairManager(hass)
    repair = _FailingRepair(hass, "failing")
    await manager.async_activate(repair)
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    manager.set_up = True
    entry = MockConfigEntry(domain=DOMAIN)
    entry.runtime_data = manager

    result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)

    assert result["repair_setup"]["last_looks"]["mock.failing"]["error"] == "KeyError"
    dumped = json.dumps(result)
    assert "grandma" not in dumped
    assert "light." not in dumped

    await manager.async_on_unload()


async def test_without_the_repairs_there_is_nothing_to_tell(
    hass: HomeAssistant,
) -> None:
    """Test an entry that never set its repairs up says so, and nothing more."""
    result = await diagnostics.async_get_config_entry_diagnostics(
        hass, MockConfigEntry(domain=DOMAIN)
    )

    assert result["repair_setup"] == {
        "state": "not_set_up",
        "modules": {},
        "last_looks": {},
    }
