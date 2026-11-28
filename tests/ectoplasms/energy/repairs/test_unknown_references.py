"""Tests for the energy dashboard unknown references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.energy.validate import (
    EnergyPreferencesValidation,
    ValidationIssues,
)
from homeassistant.exceptions import HomeAssistantError

from custom_components.spook import (
    energy_preferences,
    recorder_questions,
    statistics_sources,
)
from custom_components.spook.ectoplasms.energy.repairs.unknown_references import (
    SpookRepair,
)
from custom_components.spook.repairs import LookOutcome
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    import asyncio

    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er, issue_registry as ir

_ISSUE_ID = "energy_unknown_references_energy_unknown_references"


def _install_validation(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    result: EnergyPreferencesValidation,
) -> None:
    """Make the repair see the given validation result with energy loaded."""
    hass.config.components.add("energy")

    async def _async_validate(_hass: HomeAssistant) -> EnergyPreferencesValidation:
        return result

    monkeypatch.setattr(energy_preferences, "async_validate", _async_validate)


async def test_missing_energy_entity_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an energy source referencing a removed entity is reported."""
    result = EnergyPreferencesValidation()
    source_issues = ValidationIssues()
    source_issues.add_issue(hass, "entity_not_defined", "sensor.ghost_meter")
    # A transient issue type must not be reported.
    source_issues.add_issue(hass, "entity_unavailable", "sensor.flaky")
    result.energy_sources.append(source_issues)

    _install_validation(hass, monkeypatch, result)

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    assert "sensor.ghost_meter" in issue.translation_placeholders["entities"]
    assert "sensor.flaky" not in issue.translation_placeholders["entities"]
    # Fixable, and the fix knows exactly what was shown.
    assert issue.is_fixable
    assert issue.data
    assert issue.data["energy_unknown_entity_ids"] == "sensor.ghost_meter"
    assert issue.data["entities"] == issue.translation_placeholders["entities"]


async def test_only_transient_issues_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test transient validation issues alone produce no repair issue."""
    result = EnergyPreferencesValidation()
    device_issues = ValidationIssues()
    device_issues.add_issue(hass, "entity_unavailable", "sensor.flaky")
    result.device_consumption.append(device_issues)

    _install_validation(hass, monkeypatch, result)

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def test_energy_not_set_up_is_a_no_op(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair does nothing when the energy dashboard is absent."""
    # A fresh test instance has no energy component set up.
    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


def _install_statistics(
    monkeypatch: pytest.MonkeyPatch,
    recorded: dict[str, str | None],
) -> str:
    """Make the recorder answer for the given statistic IDs.

    Standing in for the recorder itself, which a repair test has no business
    starting: what is being pinned is which question gets asked, not how the
    database answers it.
    """
    hass_data_marker = "recorder_instance"

    async def _async_add_executor_job(
        _func: Any,
        *_args: Any,
    ) -> dict[str, tuple[int, dict[str, Any]]]:
        return {
            statistic_id: (1, {"name": name}) for statistic_id, name in recorded.items()
        }

    monkeypatch.setattr(
        recorder_questions,
        "get_instance",
        lambda hass: SimpleNamespace(  # noqa: ARG005
            async_add_executor_job=_async_add_executor_job,
        ),
    )
    monkeypatch.setattr(statistics_sources, "DATA_INSTANCE", hass_data_marker)
    return hass_data_marker


async def test_a_source_kept_by_statistics_alone_is_not_unknown(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An integration can publish statistics without an entity behind them.

    Home Assistant makes it name them after one, because importing turns away
    anything that is not a valid entity ID, so a gas meter read by a service
    somewhere arrives as `sensor.something` with no state. The energy
    dashboard draws it perfectly happily. Calling that unknown is a repair for
    a problem nobody has. #1565.

    What says it was imported is the name on the statistics. A sensor writing
    its own leaves that empty, because Home Assistant takes the name off the
    entity, and anything importing has to supply one.
    """
    result = EnergyPreferencesValidation()
    source_issues = ValidationIssues()
    source_issues.add_issue(hass, "entity_not_defined", "sensor.gas_from_a_service")
    source_issues.add_issue(hass, "entity_not_defined", "sensor.ghost_meter")
    result.energy_sources.append(source_issues)

    _install_validation(hass, monkeypatch, result)
    marker = _install_statistics(
        monkeypatch,
        {"sensor.gas_from_a_service": "Gas, read by a service"},
    )
    hass.data[marker] = object()

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    named = issue.translation_placeholders["entities"]

    assert "sensor.ghost_meter" in named
    assert "sensor.gas_from_a_service" not in named


async def test_an_entity_without_a_state_is_not_unknown_either(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Having no state covers more than having been deleted.

    An integration part way through setting up, or an entity somebody
    disabled, is registered and perfectly well known. Home Assistant reports
    it the same way because it looked for a state and found none.
    """
    entity_registry.async_get_or_create(
        "sensor",
        "demo",
        "still_here",
        suggested_object_id="quiet_for_now",
    )

    result = EnergyPreferencesValidation()
    source_issues = ValidationIssues()
    source_issues.add_issue(hass, "entity_not_defined", "sensor.quiet_for_now")
    result.energy_sources.append(source_issues)

    _install_validation(hass, monkeypatch, result)

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def test_a_deleted_entity_is_still_worth_saying(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Statistics outlive the sensor that wrote them.

    So a deleted sensor has both a registration that says deleted and rows in
    the recorder, and an energy dashboard still pointing at it is exactly what
    this is for. Leaving it out because the recorder remembers it would take
    the repair with it.
    """
    entry = entity_registry.async_get_or_create(
        "sensor",
        "demo",
        "was_here",
        suggested_object_id="removed_meter",
    )
    entity_registry.async_remove(entry.entity_id)

    result = EnergyPreferencesValidation()
    source_issues = ValidationIssues()
    source_issues.add_issue(hass, "entity_not_defined", "sensor.removed_meter")
    result.energy_sources.append(source_issues)

    _install_validation(hass, monkeypatch, result)
    marker = _install_statistics(monkeypatch, {"sensor.removed_meter": None})
    hass.data[marker] = object()

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    assert "sensor.removed_meter" in issue.translation_placeholders["entities"]


async def test_statistics_that_carry_a_name_were_put_there_by_something(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Home Assistant forgets a deleted entity after a month.

    Past that there is nothing left to say an ID was ever an entity, so the
    statistics have to answer for themselves. A sensor writing its own carries
    no name: Home Assistant takes that from the entity. One that does carry a
    name was put there by something that had to supply it, and that something
    is still doing it.

    So an integration publishing under a name a sensor used to have is
    followed rather than reported, tombstone or no tombstone.
    """
    entry = entity_registry.async_get_or_create(
        "sensor",
        "demo",
        "replaced",
        suggested_object_id="the_meter",
    )
    entity_registry.async_remove(entry.entity_id)

    result = EnergyPreferencesValidation()
    source_issues = ValidationIssues()
    source_issues.add_issue(hass, "entity_not_defined", "sensor.the_meter")
    result.energy_sources.append(source_issues)

    _install_validation(hass, monkeypatch, result)
    marker = _install_statistics(
        monkeypatch, {"sensor.the_meter": "Gas, from a service"}
    )
    hass.data[marker] = object()

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, _ISSUE_ID) is None


async def test_the_recorder_is_asked_again_on_a_clock(
    hass: HomeAssistant,
) -> None:
    """Statistics arriving or being cleared raises no event of any kind.

    Every other trigger this repair has is an event, so without a clock an
    issue raised before the first import would sit there until some unrelated
    registry change happened along.
    """
    assert SpookRepair(hass).inspect_interval is not None


async def test_a_price_entity_is_not_let_off_by_statistics(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A price is read off the state while the dashboard adds things up.

    So statistics recorded under the same name do not make one work, and
    letting it off because the recorder has something would hide a setting
    that is broken. The energy settings say which is which by their own names:
    `stat_` holds a statistic, `entity_` holds an entity that has to be there.
    """
    manager = await async_get_manager(hass)
    manager.data = {
        "energy_sources": [
            {
                "type": "gas",
                "stat_energy_from": "sensor.gas_from_a_service",
                "entity_energy_price": "sensor.the_price",
            },
        ],
        "device_consumption": [],
    }

    result = EnergyPreferencesValidation()
    source_issues = ValidationIssues()
    source_issues.add_issue(hass, "entity_not_defined", "sensor.the_price")
    result.energy_sources.append(source_issues)

    _install_validation(hass, monkeypatch, result)
    marker = _install_statistics(monkeypatch, {"sensor.the_price": "Priced elsewhere"})
    hass.data[marker] = object()

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    assert "sensor.the_price" in issue.translation_placeholders["entities"]


async def test_a_price_in_the_older_grid_form_is_not_let_off_either(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A grid connection in the older form keeps its prices inside its flows.

    Home Assistant up to 2026.9 keeps the grid that way, and a price there is
    read off the state just the same.
    """
    manager = await async_get_manager(hass)
    manager.data = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [
                    {
                        "stat_energy_from": "sensor.imported",
                        "entity_energy_price": "sensor.the_price",
                    }
                ],
                "flow_to": [],
                "cost_adjustment_day": 0.0,
            },
        ],
        "device_consumption": [],
    }

    result = EnergyPreferencesValidation()
    source_issues = ValidationIssues()
    source_issues.add_issue(hass, "entity_not_defined", "sensor.the_price")
    result.energy_sources.append(source_issues)

    _install_validation(hass, monkeypatch, result)
    marker = _install_statistics(monkeypatch, {"sensor.the_price": "Priced elsewhere"})
    hass.data[marker] = object()

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    assert "sensor.the_price" in issue.translation_placeholders["entities"]


async def _flush_debouncer(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance past the inspection debouncer cooldown and let it fire."""
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_saving_the_energy_settings_gets_a_look(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the issue goes once the energy settings are fixed and saved.

    Picking another entity in the energy settings changes nothing in the
    registries, so nothing else tells the repair to look again. #2067.
    """
    result = EnergyPreferencesValidation()
    source_issues = ValidationIssues()
    source_issues.add_issue(hass, "entity_not_defined", "sensor.ghost_meter")
    result.energy_sources.append(source_issues)
    _install_validation(hass, monkeypatch, result)

    repair = SpookRepair(hass)
    await repair.async_activate()
    await _flush_debouncer(hass, freezer)
    assert async_issue_about(issue_registry, _ISSUE_ID)

    # The settings are fixed, and saved the way the energy panel saves them.
    _install_validation(hass, monkeypatch, EnergyPreferencesValidation())
    await (await async_get_manager(hass)).async_update({"energy_sources": []})
    await _flush_debouncer(hass, freezer)

    assert async_issue_about(issue_registry, _ISSUE_ID) is None

    await repair.async_deactivate()


async def test_a_deactivated_repair_no_longer_follows_the_energy_settings(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test saving the energy settings reaches no repair that was deactivated."""
    _install_validation(hass, monkeypatch, EnergyPreferencesValidation())

    repair = SpookRepair(hass)
    await repair.async_activate()
    await _flush_debouncer(hass, freezer)
    await repair.async_deactivate()

    # Counted at the debouncer, not at the inspection: deactivating shuts the
    # debouncer down, so a save that still reached the repair would never
    # show up as an inspection.
    calls = 0

    async def _count() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(repair, "inspect_debouncer", SimpleNamespace(async_call=_count))
    await (await async_get_manager(hass)).async_update({"energy_sources": []})
    await hass.async_block_till_done()

    assert calls == 0


async def test_the_energy_settings_are_followed_once(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test looking again and again puts one listener in, not one per look.

    Home Assistant has no way to take a listener out, so every extra one
    would stay for as long as it runs.
    """
    _install_validation(hass, monkeypatch, EnergyPreferencesValidation())
    listening: list[Any] = []
    manager = await async_get_manager(hass)
    monkeypatch.setattr(manager, "async_listen_updates", listening.append)

    await SpookRepair(hass).async_inspect()
    await SpookRepair(hass).async_inspect()

    assert len(listening) == 1


async def test_following_the_energy_settings_is_tried_again_after_a_failure(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test energy settings that failed to load once are followed the next time."""
    real_get_manager = energy_preferences.async_get_manager
    listening: list[Any] = []
    manager = await real_get_manager(hass)
    monkeypatch.setattr(manager, "async_listen_updates", listening.append)

    async def _fails(_hass: HomeAssistant) -> Any:
        message = "The energy settings could not be loaded"
        raise HomeAssistantError(message)

    monkeypatch.setattr(energy_preferences, "async_get_manager", _fails)
    with pytest.raises(HomeAssistantError):
        await energy_preferences.async_follow_energy_settings(hass)
    assert not listening

    monkeypatch.setattr(energy_preferences, "async_get_manager", real_get_manager)
    await energy_preferences.async_follow_energy_settings(hass)

    assert len(listening) == 1


async def test_a_recorder_too_slow_to_answer_could_not_look(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a recorder that does not answer in time keeps what is up.

    Without the statistics, a source imported by an integration looks
    unknown. Judged on half the answer, the round would report it, or a
    clean one would take down what is up.
    """
    result = EnergyPreferencesValidation()
    source_issues = ValidationIssues()
    source_issues.add_issue(hass, "entity_not_defined", "sensor.ghost_meter")
    result.energy_sources.append(source_issues)
    _install_validation(hass, monkeypatch, result)
    marker = _install_statistics(monkeypatch, {})
    hass.data[marker] = object()

    repair = SpookRepair(hass)
    # pylint: disable-next=protected-access
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, _ISSUE_ID)

    never_answered: asyncio.Future[Any] = hass.loop.create_future()
    monkeypatch.setattr(
        recorder_questions,
        "get_instance",
        lambda _hass: SimpleNamespace(async_add_executor_job=lambda *_: never_answered),
    )
    monkeypatch.setattr(recorder_questions, "RECORDER_ANSWERS_WITHIN", 0.01)

    # pylint: disable-next=protected-access
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert async_issue_about(issue_registry, _ISSUE_ID)
    assert repair.last_look
    assert repair.last_look.outcome is LookOutcome.COULD_NOT_LOOK

    never_answered.set_result({})
