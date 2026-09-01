"""Tests for the energy dashboard unknown references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.energy.validate import (
    EnergyPreferencesValidation,
    ValidationIssues,
)

from custom_components.spook import statistics_sources
from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.energy.repairs import unknown_references
from custom_components.spook.ectoplasms.energy.repairs.unknown_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er, issue_registry as ir
    import pytest

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

    monkeypatch.setattr(unknown_references, "async_validate", _async_validate)


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

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    assert "sensor.ghost_meter" in issue.translation_placeholders["entities"]
    assert "sensor.flaky" not in issue.translation_placeholders["entities"]


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

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_energy_not_set_up_is_a_no_op(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair does nothing when the energy dashboard is absent."""
    # A fresh test instance has no energy component set up.
    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


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
        statistics_sources,
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

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
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

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


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

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
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

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


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

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    assert "sensor.the_price" in issue.translation_placeholders["entities"]
