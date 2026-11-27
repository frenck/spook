"""Tests for the empty areas, empty floors and unused labels repairs and reloads.

An existing automation or script, edited, is no new entity and no registry
change: what says it changed is its reload being done.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, NamedTuple

from homeassistant.helpers import (
    area_registry as ar,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs import (
    empty_areas,
    empty_floors,
    unused_labels,
)

from tests.repair_helpers import (
    async_reload_slower_than_the_repair_waits,
    async_wait_out_the_repair,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

    from custom_components.spook.repairs import AbstractSpookRepair

# Comfortably past the creation grace period.
_AGED = timedelta(days=2)

_SOMETHING_ELSE = {"entity_id": "light.porch"}


class _Reported(NamedTuple):
    """A repair, what makes the thing it reports, and how a target names it."""

    repair_class: type[AbstractSpookRepair]
    create: Callable[[HomeAssistant], str]
    target_key: str


def _new_area(hass: HomeAssistant) -> str:
    """Create an area, and return its ID."""
    return ar.async_get(hass).async_create("Attic").id


def _new_floor(hass: HomeAssistant) -> str:
    """Create a floor, and return its ID."""
    return fr.async_get(hass).async_create("Attic").floor_id


def _new_label(hass: HomeAssistant) -> str:
    """Create a label, and return its ID."""
    return lr.async_get(hass).async_create("Attic").label_id


_REPORTED = pytest.mark.parametrize(
    "reported",
    [
        _Reported(empty_areas.SpookRepair, _new_area, "area_id"),
        _Reported(empty_floors.SpookRepair, _new_floor, "floor_id"),
        _Reported(unused_labels.SpookRepair, _new_label, "label_id"),
    ],
    ids=["empty_areas", "empty_floors", "unused_labels"],
)


def _automations(target: dict[str, str]) -> dict[str, Any]:
    """Return a configuration holding one automation, with an ID."""
    return {
        "automation": [
            {
                "id": "lights",
                "alias": "Lights",
                "triggers": [{"trigger": "event", "event_type": "spook"}],
                "actions": [{"action": "light.turn_on", "target": target}],
            }
        ]
    }


def _scripts(target: dict[str, str]) -> dict[str, Any]:
    """Return a configuration holding one script."""
    return {
        "script": {
            "lights": {"sequence": [{"action": "light.turn_on", "target": target}]}
        }
    }


_CONFIGURED = pytest.mark.parametrize("configured", [_automations, _scripts])


async def _set_up(hass: HomeAssistant, configuration: dict[str, Any]) -> None:
    """Set up the one domain in a configuration."""
    (domain,) = configuration
    assert await async_setup_component(hass, domain, configuration)
    await hass.async_block_till_done()


async def _activated(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, reported: _Reported
) -> AbstractSpookRepair:
    """Activate the repair, and let its first look run."""
    repair = reported.repair_class(hass)
    await repair.async_activate()
    await async_wait_out_the_repair(hass, freezer)
    return repair


@_REPORTED
@_CONFIGURED
async def test_a_reload_that_starts_using_it_takes_the_issue_away(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    reported: _Reported,
    configured: Callable[[dict[str, str]], dict[str, Any]],
) -> None:
    """Test an edited automation or script, once reloaded, takes the issue away.

    The look the reload call brought came while the YAML was still being
    read, and nothing brought one once the reload was done. The issue stayed
    up, with a button to remove what is now used, until something unrelated
    brought a look, or the daily one did.
    """
    thing_id = reported.create(hass)
    issue = (DOMAIN, f"{reported.repair_class.repair}_{thing_id}")
    freezer.tick(_AGED)
    await _set_up(hass, configured(_SOMETHING_ELSE))
    repair = await _activated(hass, freezer, reported)
    assert issue in issue_registry.issues

    await async_reload_slower_than_the_repair_waits(
        hass, freezer, configured({reported.target_key: thing_id})
    )
    await repair.async_deactivate()

    assert issue not in issue_registry.issues


@_REPORTED
@_CONFIGURED
async def test_a_reload_that_stops_using_it_raises_the_issue(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    reported: _Reported,
    configured: Callable[[dict[str, str]], dict[str, Any]],
) -> None:
    """Test a reload taking the last use away reports the thing unused."""
    thing_id = reported.create(hass)
    issue = (DOMAIN, f"{reported.repair_class.repair}_{thing_id}")
    freezer.tick(_AGED)
    await _set_up(hass, configured({reported.target_key: thing_id}))
    repair = await _activated(hass, freezer, reported)
    assert issue not in issue_registry.issues

    await async_reload_slower_than_the_repair_waits(
        hass, freezer, configured(_SOMETHING_ELSE)
    )
    await repair.async_deactivate()

    assert issue in issue_registry.issues
