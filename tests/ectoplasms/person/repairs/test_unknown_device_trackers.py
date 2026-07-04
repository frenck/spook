"""Tests for the person unknown device trackers repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import DATA_INSTANCES

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.person.repairs.unknown_device_trackers import (
    SpookRepair,
)
from custom_components.spook.repairs import (
    PersonUnknownDeviceTrackerFixFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers import entity_registry as er, issue_registry as ir

_ISSUE_ID = "person_unknown_device_trackers_person.frenck"


def _install_person(hass: HomeAssistant, device_trackers: list[str]) -> None:
    """Install a fake person entity component into hass."""
    person = SimpleNamespace(
        entity_id="person.frenck",
        name="Frenck",
        device_trackers=device_trackers,
    )
    hass.data.setdefault(DATA_INSTANCES, {})["person"] = SimpleNamespace(
        entities=[person]
    )


def _flow_for(
    hass: HomeAssistant, unknown: list[str]
) -> PersonUnknownDeviceTrackerFixFlow:
    """Build a person fix flow as the framework would wire it up."""
    flow = PersonUnknownDeviceTrackerFixFlow()
    flow.hass = hass
    flow.issue_id = _ISSUE_ID
    flow.data = {
        "person_entity_id": "person.frenck",
        "person": "Frenck",
        "device_trackers": "- `" + "`\n- `".join(unknown) + "`",
        "unknown_trackers": ",".join(unknown),
    }
    return flow


async def test_unknown_device_tracker_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a person tracking a non-existing device tracker is reported."""
    hass.states.async_set("device_tracker.phone", "home")
    _install_person(hass, ["device_tracker.gone", "device_tracker.phone"])

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.is_fixable
    assert issue.translation_placeholders == {"person": "Frenck"}
    assert issue.data == {
        "person_entity_id": "person.frenck",
        "person": "Frenck",
        "device_trackers": "- `device_tracker.gone`",
        "unknown_trackers": "device_tracker.gone",
    }


async def test_registered_device_tracker_is_not_flagged(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device tracker known only to the registry is left alone."""
    entry = entity_registry.async_get_or_create("device_tracker", "gps", "car")
    _install_person(hass, [entry.entity_id])

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_all_known_trackers_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a person with only existing device trackers is not reported."""
    hass.states.async_set("device_tracker.phone", "home")
    _install_person(hass, ["device_tracker.phone"])

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_no_person_component_does_nothing(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair is a no-op when person is not set up."""
    await SpookRepair(hass).async_inspect()

    assert not any(
        issue_id.startswith("person_unknown_device_trackers_")
        for domain, issue_id in issue_registry.issues
        if domain == DOMAIN
    )


async def test_fix_flow_remove_calls_service(
    hass: HomeAssistant,
) -> None:
    """Test the remove option strips the still-unknown trackers."""
    calls: list[dict] = []

    async def _handler(call: ServiceCall) -> None:
        calls.append(call.data)

    hass.services.async_register("person", "remove_device_tracker", _handler)

    flow = await async_create_fix_flow(
        hass,
        _ISSUE_ID,
        {
            "person_entity_id": "person.frenck",
            "person": "Frenck",
            "device_trackers": "- `device_tracker.gone`",
            "unknown_trackers": "device_tracker.gone",
        },
    )
    assert isinstance(flow, PersonUnknownDeviceTrackerFixFlow)
    flow.hass = hass
    flow.data = {
        "person_entity_id": "person.frenck",
        "person": "Frenck",
        "device_trackers": "- `device_tracker.gone`",
        "unknown_trackers": "device_tracker.gone",
    }

    result = await flow.async_step_remove()

    assert result["type"] == "create_entry"
    assert calls == [
        {"entity_id": "person.frenck", "device_tracker": ["device_tracker.gone"]}
    ]


async def test_fix_flow_remove_skips_now_known_tracker(
    hass: HomeAssistant,
) -> None:
    """Test a tracker that came back is not removed."""
    hass.states.async_set("device_tracker.gone", "home")
    called = False

    async def _handler(_call: ServiceCall) -> None:
        nonlocal called
        called = True

    hass.services.async_register("person", "remove_device_tracker", _handler)

    flow = _flow_for(hass, ["device_tracker.gone"])
    result = await flow.async_step_remove()

    assert result["type"] == "create_entry"
    assert called is False


async def test_fix_flow_remove_yaml_person_aborts(
    hass: HomeAssistant,
) -> None:
    """Test a non-editable person reports it cannot be edited."""

    async def _handler(_call: ServiceCall) -> None:
        raise HomeAssistantError

    hass.services.async_register("person", "remove_device_tracker", _handler)

    flow = _flow_for(hass, ["device_tracker.gone"])
    result = await flow.async_step_remove()

    assert result["type"] == "abort"
    assert result["reason"] == "not_editable"
