"""Tests for the dead entities repair."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_RESTORED, STATE_UNAVAILABLE
from homeassistant.core import State

from homeassistant.data_entry_flow import FlowResultType

from custom_components.spook.const import DOMAIN
from custom_components.spook.repairs import DeadEntitiesFixFlow, async_create_fix_flow
from custom_components.spook.ectoplasms.homeassistant.repairs.dead_entities import (
    SpookRepair,
)
from tests.repair_helpers import async_count_scheduled_inspections

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er, issue_registry as ir


def _loaded_entry(
    hass: HomeAssistant, title: str = "Somebody's account"
) -> MockConfigEntry:
    """Add a loaded config entry to hass.

    The title is deliberately not the integration's name, because for an
    account-based integration it never is.
    """
    entry = MockConfigEntry(domain="derivative", title=title)
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry


def _register_restored(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry | None,
    object_id: str,
) -> str:
    """Register an entity with a restored unavailable state."""
    reg = entity_registry.async_get_or_create(
        "sensor",
        "hue",
        object_id,
        config_entry=entry,
    )
    hass.states.async_set(reg.entity_id, STATE_UNAVAILABLE, {ATTR_RESTORED: True})
    return reg.entity_id


def _register_living(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    object_id: str = "living",
) -> str:
    """Register an entity of this entry that actually turned up.

    Most tests want one. The repair only speaks up once something of a config
    entry has real data, since an integration that is loaded but still waiting
    for its first push has everything restored and nothing wrong with it.
    """
    reg = entity_registry.async_get_or_create(
        "sensor",
        "hue",
        object_id,
        config_entry=entry,
    )
    hass.states.async_set(reg.entity_id, "21.5")
    return reg.entity_id


async def test_dead_entity_of_loaded_entry_is_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a restored entity of a loaded entry is reported."""
    entry = _loaded_entry(hass)
    _register_living(hass, entity_registry, entry)
    dead = _register_restored(hass, entity_registry, entry, "dead")

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["entities"] == f"- `{dead}`"
    assert issue.translation_placeholders["integration"] == "Derivative", (
        "it named the config entry rather than the integration"
    )
    assert issue.is_fixable, "there is nothing a person can do with this by hand"


async def test_live_entity_is_not_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entity with a real state is not reported."""
    entry = _loaded_entry(hass)
    reg = entity_registry.async_get_or_create(
        "sensor", "hue", "live", config_entry=entry
    )
    hass.states.async_set(reg.entity_id, "21")

    await SpookRepair(hass).async_inspect()

    assert (
        issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
        is None
    )


async def test_restored_entity_of_retrying_entry_is_not_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a restored entity of a retrying entry is not reported.

    A config entry that has not finished loading may still provide the
    entity, so it must not be flagged as dead.
    """
    entry = MockConfigEntry(domain="derivative", title="Hue")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)
    _register_restored(hass, entity_registry, entry, "maybe")

    await SpookRepair(hass).async_inspect()

    assert (
        issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
        is None
    )


async def test_restored_entity_without_config_entry_is_not_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a restored entity with no config entry is not reported.

    Without a config entry its load state cannot be confirmed, so it is
    deliberately left alone.
    """
    _register_restored(hass, entity_registry, None, "yamlish")

    await SpookRepair(hass).async_inspect()

    assert not any(
        issue_id.startswith("dead_entities_")
        for domain, issue_id in issue_registry.issues
        if domain == DOMAIN
    )


async def test_entity_dying_mid_session_is_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entity that dies while its entry stays loaded is reported.

    Home Assistant writes the restored placeholder when an entity is removed
    but its registry entry survives. The entity registry does not change and
    the config entry stays loaded, so nothing else marks the moment.
    """
    entry = _loaded_entry(hass)
    _register_living(hass, entity_registry, entry)
    reg = entity_registry.async_get_or_create(
        "sensor", "hue", "dies", config_entry=entry
    )
    hass.states.async_set(reg.entity_id, "21.5")
    repair = SpookRepair(hass)

    await repair._async_inspect_with_cleanup()
    assert (
        issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
        is None
    )

    hass.states.async_set(reg.entity_id, STATE_UNAVAILABLE, {ATTR_RESTORED: True})
    await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")


async def test_issue_clears_when_the_entity_finally_appears(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue goes away once the entity shows up for real."""
    entry = _loaded_entry(hass)
    _register_living(hass, entity_registry, entry)
    dead = _register_restored(hass, entity_registry, entry, "late")
    repair = SpookRepair(hass)

    await repair._async_inspect_with_cleanup()
    assert issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")

    hass.states.async_set(dead, "21.5")
    await repair._async_inspect_with_cleanup()

    assert (
        issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
        is None
    )


async def _count_scheduled_inspections(
    hass: HomeAssistant,
    old_state: State | None,
    new_state: State | None,
) -> int:
    """Return how many inspections one state change schedules."""
    repair = SpookRepair(hass)
    await repair.async_activate()

    return await async_count_scheduled_inspections(
        hass, repair, "sensor.hue_thing", old_state, new_state
    )


def _restored(entity_id: str = "sensor.hue_thing") -> State:
    """Return the restored placeholder state Home Assistant writes."""
    return State(entity_id, STATE_UNAVAILABLE, {ATTR_RESTORED: True})


def _live(entity_id: str = "sensor.hue_thing", state: str = "21.5") -> State:
    """Return an ordinary state."""
    return State(entity_id, state)


async def test_entering_the_restored_state_rechecks(hass: HomeAssistant) -> None:
    """Test an entity dying into the placeholder schedules an inspection."""
    assert await _count_scheduled_inspections(hass, _live(), _restored()) == 1


async def test_leaving_the_restored_state_rechecks(hass: HomeAssistant) -> None:
    """Test an entity coming back for real schedules an inspection."""
    assert await _count_scheduled_inspections(hass, _restored(), _live()) == 1


async def test_appearing_as_restored_rechecks(hass: HomeAssistant) -> None:
    """Test the placeholder being written from nothing schedules an inspection."""
    assert await _count_scheduled_inspections(hass, None, _restored()) == 1


async def test_ordinary_state_change_does_not_recheck(hass: HomeAssistant) -> None:
    """Test a normal state change schedules nothing.

    This is the one that matters for cost: entities change state constantly,
    and this repair walks every state in the machine.
    """
    assert await _count_scheduled_inspections(hass, _live(), _live(state="22.0")) == 0


async def test_entity_appearing_normally_does_not_recheck(hass: HomeAssistant) -> None:
    """Test an entity appearing without a placeholder schedules nothing.

    The false-positive twin for the filter. A brand new entity was never
    dead, so its arrival says nothing about a dead one.
    """
    assert await _count_scheduled_inspections(hass, None, _live()) == 0


async def test_entity_removed_outright_does_not_recheck(hass: HomeAssistant) -> None:
    """Test an entity removed along with its registry entry schedules nothing.

    No placeholder is left behind in that case, so there is nothing for this
    repair to find.
    """
    assert await _count_scheduled_inspections(hass, _live(), None) == 0


async def test_the_fix_clears_out_the_leftover_registrations(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Which is the only place these entities still exist.

    The old advice was to go and remove them from the entity registry, which
    asks somebody to know what an entity registry is and where to find it.
    """
    entry = _loaded_entry(hass)
    _register_living(hass, entity_registry, entry)
    dead = _register_restored(hass, entity_registry, entry, "dead")
    other = _register_restored(hass, entity_registry, None, "not_this_one")

    flow = await async_create_fix_flow(
        hass,
        f"dead_entities_{entry.entry_id}",
        {"dead_entities_config_entry_id": entry.entry_id},
    )
    assert isinstance(flow, DeadEntitiesFixFlow), (
        "the issue would fall back to a plain confirm dialog"
    )
    flow.hass = hass
    flow.data = {"dead_entities_config_entry_id": entry.entry_id}

    result = await flow.async_step_remove()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entity_registry.async_get(dead) is None
    assert entity_registry.async_get(other) is not None, "it took one that was not its"


async def test_the_fix_leaves_an_entity_that_came_back(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """An issue can sit in front of somebody for a while.

    An entity that turned up again in the meantime is a working entity, and
    deleting its registration would take its history and settings with it.
    """
    entry = _loaded_entry(hass)
    _register_living(hass, entity_registry, entry)
    dead = _register_restored(hass, entity_registry, entry, "dead")
    returned = _register_restored(hass, entity_registry, entry, "returned")

    hass.states.async_set(returned, "21.5")

    flow = DeadEntitiesFixFlow()
    flow.hass = hass
    flow.data = {"dead_entities_config_entry_id": entry.entry_id}

    await flow.async_step_remove()

    assert entity_registry.async_get(dead) is None
    assert entity_registry.async_get(returned) is not None


async def test_an_integration_still_waiting_for_its_first_data_is_not_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Loaded is not the same as having data.

    An integration fed by a webhook, Ecowitt among them, sets up in a moment
    and then waits for the device to push, which can be minutes. Everything it
    registered sits restored and unavailable in the meantime. Reporting that
    tells somebody their weather station is gone while it is between
    readings, and with a fix button attached they can throw the lot away.
    """
    entry = _loaded_entry(hass)
    for name in ("temperature", "humidity", "wind"):
        _register_restored(hass, entity_registry, entry, name)

    await SpookRepair(hass).async_inspect()

    assert (
        issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
        is None
    ), "it reported an integration that had simply not been pushed to yet"


async def test_once_the_data_arrives_what_is_still_missing_is_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """One entity through the door says the rest are not coming.

    A sensor removed at the station is a real leftover, and by then there is
    something to tell it apart from an integration that has not started
    talking yet.
    """
    entry = _loaded_entry(hass)
    for name in ("temperature", "humidity"):
        _register_restored(hass, entity_registry, entry, name)
    _register_living(hass, entity_registry, entry, "wind")

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
    assert issue
    assert issue.translation_placeholders
    assert "temperature" in issue.translation_placeholders["entities"]
    assert "wind" not in issue.translation_placeholders["entities"]


async def test_the_fix_stands_down_while_the_integration_is_reloading(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Everything of a reloading integration looks missing while that lasts.

    The issue may have been sitting there since before the reload started, so
    acting on it then would delete entities that are on their way back. The
    inspection already refuses to look at entries that are not loaded; the fix
    has to as well.
    """
    entry = _loaded_entry(hass)
    dead = _register_restored(hass, entity_registry, entry, "dead")
    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)

    flow = DeadEntitiesFixFlow()
    flow.hass = hass
    flow.data = {"dead_entities_config_entry_id": entry.entry_id}

    result = await flow.async_step_remove()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"
    assert entity_registry.async_get(dead) is not None


async def test_an_integration_with_nothing_left_is_reported_in_the_end(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Waiting for a living sibling alone would never report some of these.

    An integration with one entity, or an account whose every device was
    removed, has nothing living to point at and never would. It gets an hour
    to produce something, which is longer than any device that pushes on its
    own schedule takes, and then the silence is taken at face value.
    """
    entry = _loaded_entry(hass)
    _register_restored(hass, entity_registry, entry, "the_only_one")
    repair = SpookRepair(hass)

    await repair.async_inspect()
    assert (
        issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
        is None
    ), "it gave up on the integration before it had a chance"

    freezer.tick(timedelta(hours=1, minutes=1))
    await repair.async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, f"dead_entities_{entry.entry_id}")
