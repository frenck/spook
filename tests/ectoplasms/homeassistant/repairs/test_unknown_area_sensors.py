"""Tests for the unknown area sensors repair."""

# pylint: disable=wrong-import-order,protected-access
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.data_entry_flow import FlowResultType

from custom_components.spook.entity_filtering import (
    async_setup_all_entity_ids_cache_invalidation,
)
from custom_components.spook.ectoplasms.homeassistant.repairs.unknown_area_sensors import (
    SpookRepair,
)
from custom_components.spook.repairs import (
    AreaUnknownSensorsFixFlow,
    async_create_fix_flow,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        area_registry as ar,
        entity_registry as er,
        issue_registry as ir,
    )


def _sensor(hass: HomeAssistant, entity_id: str, device_class: str) -> None:
    """Put a sensor of this kind in the state machine."""
    hass.states.async_set(entity_id, "20", {"device_class": device_class})


def _kitchen(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    *,
    temperature: str | None = None,
    humidity: str | None = None,
) -> ar.AreaEntry:
    """Create a kitchen with these sensors, the way the UI sets them.

    Home Assistant only accepts a sensor that exists and is the right kind,
    so they are put in place first, like a real one would be.
    """
    if temperature:
        _sensor(hass, temperature, "temperature")
    if humidity:
        _sensor(hass, humidity, "humidity")
    area = area_registry.async_create("Kitchen")
    return area_registry.async_update(
        area.id, temperature_entity_id=temperature, humidity_entity_id=humidity
    )


def _issue_id(area: ar.AreaEntry) -> str:
    """Return the registry issue ID for an area."""
    return f"unknown_area_sensors_{area.id}"


async def test_a_removed_temperature_sensor_is_reported(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The area keeps pointing at a sensor that is not there anymore."""
    area = _kitchen(hass, area_registry, temperature="sensor.kitchen_temperature")
    hass.states.async_remove("sensor.kitchen_temperature")

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, _issue_id(area))
    assert issue
    assert issue.is_fixable
    assert issue.translation_placeholders
    assert issue.translation_placeholders["sensors"] == "temperature"
    assert "sensor.kitchen_temperature" in issue.translation_placeholders["entities"]


async def test_both_sensors_gone_are_named_together(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """One issue per area, naming each setting that points at nothing."""
    area = _kitchen(
        hass,
        area_registry,
        temperature="sensor.kitchen_temperature",
        humidity="sensor.kitchen_humidity",
    )
    hass.states.async_remove("sensor.kitchen_temperature")
    hass.states.async_remove("sensor.kitchen_humidity")

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, _issue_id(area))
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["sensors"] == "temperature and humidity"


async def test_sensors_that_exist_are_left_alone(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Nothing to report while both sensors are there."""
    area = _kitchen(
        hass,
        area_registry,
        temperature="sensor.kitchen_temperature",
        humidity="sensor.kitchen_humidity",
    )

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, _issue_id(area)) is None


async def test_a_sensor_in_the_registry_without_a_state_is_not_missing(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Still loading, or disabled: it is there, just not running right now."""
    entity_registry.async_get_or_create(
        "sensor", "test", "temp", suggested_object_id="kitchen_temperature"
    )
    area = _kitchen(hass, area_registry, temperature="sensor.kitchen_temperature")
    hass.states.async_remove("sensor.kitchen_temperature")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, _issue_id(area)) is None


async def test_the_issue_goes_once_the_sensor_is_back(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Fixed by hand, or the sensor returned: the issue cleans itself up.

    Spook forgets which entities exist whenever one comes or goes; set up
    here the way Spook sets it up, or the sensor coming back goes unseen.
    """
    async_setup_all_entity_ids_cache_invalidation(hass)
    area = _kitchen(hass, area_registry, temperature="sensor.kitchen_temperature")
    hass.states.async_remove("sensor.kitchen_temperature")
    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, _issue_id(area))

    _sensor(hass, "sensor.kitchen_temperature", "temperature")
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert async_issue_about(issue_registry, _issue_id(area)) is None


async def test_fix_flow_clears_only_what_points_at_nothing(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """The missing sensor is cleared, the one that exists is kept."""
    area = _kitchen(
        hass,
        area_registry,
        temperature="sensor.kitchen_temperature",
        humidity="sensor.kitchen_humidity",
    )
    hass.states.async_remove("sensor.kitchen_temperature")

    flow = await async_create_fix_flow(
        hass, _issue_id(area), {"area_sensors_area_id": area.id, "area": "Kitchen"}
    )
    assert isinstance(flow, AreaUnknownSensorsFixFlow)
    flow.hass = hass
    flow.data = {
        "area_sensors_area_id": area.id,
        "area_sensors_fields": "temperature_entity_id,humidity_entity_id",
    }

    result = await flow.async_step_remove()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    updated = area_registry.async_get_area(area.id)
    assert updated is not None
    assert updated.temperature_entity_id is None
    assert updated.humidity_entity_id == "sensor.kitchen_humidity"


async def test_fix_flow_menu_names_the_area_and_the_sensor(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The menu is handed the issue's data, and names what it is about."""
    area = _kitchen(hass, area_registry, temperature="sensor.kitchen_temperature")
    hass.states.async_remove("sensor.kitchen_temperature")
    await SpookRepair(hass).async_inspect()
    issue = async_issue_about(issue_registry, _issue_id(area))
    assert issue is not None

    flow = AreaUnknownSensorsFixFlow()
    flow.hass = hass
    flow.data = issue.data

    result = await flow.async_step_init()

    assert result["type"] == FlowResultType.MENU
    placeholders = result["description_placeholders"]
    assert placeholders is not None
    assert placeholders["area"] == "Kitchen"
    assert placeholders["sensors"] == "temperature"
    assert "sensor.kitchen_temperature" in placeholders["entities"]


async def test_fix_flow_clears_only_the_settings_it_showed(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """A setting that broke after the issue was raised is not cleared.

    The issue showed the temperature sensor. It came back, and the humidity
    sensor went missing, before the button was pressed. Clearing humidity
    would be clearing something nobody was shown.
    """
    area = _kitchen(
        hass,
        area_registry,
        temperature="sensor.kitchen_temperature",
        humidity="sensor.kitchen_humidity",
    )
    hass.states.async_remove("sensor.kitchen_humidity")

    flow = AreaUnknownSensorsFixFlow()
    flow.hass = hass
    flow.data = {
        "area_sensors_area_id": area.id,
        "area_sensors_fields": "temperature_entity_id",
    }

    await flow.async_step_remove()

    updated = area_registry.async_get_area(area.id)
    assert updated is not None
    assert updated.temperature_entity_id == "sensor.kitchen_temperature"
    assert updated.humidity_entity_id == "sensor.kitchen_humidity"


async def test_the_same_sensor_on_the_other_setting_is_a_new_finding(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Ignoring it on one setting does not ignore it on the other.

    The issue ID follows what was found, and which setting points at the
    sensor is part of that.
    """
    area = _kitchen(hass, area_registry, temperature="sensor.kitchen_climate")
    hass.states.async_remove("sensor.kitchen_climate")
    await SpookRepair(hass).async_inspect()
    before = async_issue_about(issue_registry, _issue_id(area))
    assert before

    hass.states.async_set("sensor.kitchen_climate", "50", {"device_class": "humidity"})
    area_registry.async_update(
        area.id, temperature_entity_id=None, humidity_entity_id="sensor.kitchen_climate"
    )
    hass.states.async_remove("sensor.kitchen_climate")
    for issue_id in list(issue_registry.issues):
        issue_registry.async_delete(*issue_id)
    await SpookRepair(hass).async_inspect()
    after = async_issue_about(issue_registry, _issue_id(area))

    assert after
    assert after.issue_id != before.issue_id
