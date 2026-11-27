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
from tests.repair_helpers import (
    async_delete_entity,
    async_forget_deleted_entities,
    async_issue_about,
    wire_fix_flow,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

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
    assert issue.translation_key == "unknown_area_sensors_temperature"
    assert "sensor.kitchen_temperature" in issue.translation_placeholders["entities"]


async def test_a_removed_humidity_sensor_is_reported(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The humidity setting gets its own text, not the temperature one."""
    area = _kitchen(hass, area_registry, humidity="sensor.kitchen_humidity")
    hass.states.async_remove("sensor.kitchen_humidity")

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, _issue_id(area))
    assert issue
    assert issue.translation_key == "unknown_area_sensors_humidity"


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
    assert issue.translation_key == "unknown_area_sensors_both"


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
    _gone(hass, "sensor.kitchen_temperature", deleted=True)

    flow = await async_create_fix_flow(
        hass, _issue_id(area), {"area_sensors_area_id": area.id, "area": "Kitchen"}
    )
    assert isinstance(flow, AreaUnknownSensorsFixFlow)
    flow.hass = hass
    flow.data = {
        "area_sensors_area_id": area.id,
        "area_sensors_references": (
            "temperature_entity_id:sensor.kitchen_temperature,"
            "humidity_entity_id:sensor.kitchen_humidity"
        ),
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
    assert "sensors" not in placeholders
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
    _gone(hass, "sensor.kitchen_humidity", deleted=True)

    flow = AreaUnknownSensorsFixFlow()
    flow.hass = hass
    flow.data = {
        "area_sensors_area_id": area.id,
        "area_sensors_references": "temperature_entity_id:sensor.kitchen_temperature",
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


async def test_a_setting_pointed_elsewhere_since_is_not_cleared(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a replacement sensor that went missing too is not cleared.

    The issue named the old temperature sensor. Somebody set a new one, which
    is missing as well by the time the button is pressed. That setting is not
    the one they saw.
    """
    async_setup_all_entity_ids_cache_invalidation(hass)
    area = _kitchen(hass, area_registry, temperature="sensor.kitchen_temperature")
    _gone(hass, "sensor.kitchen_temperature", deleted=True)
    await SpookRepair(hass).async_inspect()
    issue = async_issue_about(issue_registry, _issue_id(area))
    assert issue

    flow = AreaUnknownSensorsFixFlow()
    flow.hass = hass
    flow.data = issue.data
    # Home Assistant only takes a sensor that exists, so it does, and then
    # it is deleted as well.
    _sensor(hass, "sensor.new_one", "temperature")
    area_registry.async_update(area.id, temperature_entity_id="sensor.new_one")
    _gone(hass, "sensor.new_one", deleted=True)
    result = await flow.async_step_remove()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "changed"
    assert area_registry.async_get_area(area.id).temperature_entity_id == (
        "sensor.new_one"
    )


_TEMPERATURE = "sensor.kitchen_temperature"
_HUMIDITY = "sensor.kitchen_humidity"


def _gone(hass: HomeAssistant, entity_id: str, *, deleted: bool) -> None:
    """Take a sensor away, deleted from Home Assistant or just not there.

    The state goes first: Home Assistant hands out no entity ID that a
    state is still using.
    """
    hass.states.async_remove(entity_id)
    if deleted:
        async_delete_entity(hass, entity_id)


async def _flow_for_the_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    area: ar.AreaEntry,
) -> AreaUnknownSensorsFixFlow:
    """Look, and return the fix flow of the issue raised about the area."""
    await SpookRepair(hass).async_inspect()
    issue = async_issue_about(issue_registry, _issue_id(area))
    assert issue

    flow = wire_fix_flow(hass, AreaUnknownSensorsFixFlow(), issue.issue_id)
    flow.data = issue.data
    return flow


async def test_a_sensor_that_may_not_be_up_yet_gets_no_clear_button(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a sensor Home Assistant never deleted keeps its setting.

    A YAML sensor without a unique ID whose platform is still retrying has
    no state and no registry entry. So has one that is gone.
    """
    area = _kitchen(hass, area_registry, temperature=_TEMPERATURE)
    _gone(hass, _TEMPERATURE, deleted=False)

    flow = await _flow_for_the_issue(hass, issue_registry, area)
    menu = await flow.async_step_init()
    result = await flow.async_step_remove()

    assert menu["menu_options"] == ["manage", "ignore"]
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "changed"
    updated = area_registry.async_get_area(area.id)
    assert updated
    assert updated.temperature_entity_id == _TEMPERATURE


async def test_a_sensor_deleted_from_home_assistant_can_be_cleared(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a sensor the entity registry deleted keeps its clear button."""
    area = _kitchen(hass, area_registry, temperature=_TEMPERATURE)
    _gone(hass, _TEMPERATURE, deleted=True)

    flow = await _flow_for_the_issue(hass, issue_registry, area)
    menu = await flow.async_step_init()
    result = await flow.async_step_remove()

    assert menu["menu_options"] == ["remove", "manage", "ignore"]
    assert result["type"] is FlowResultType.CREATE_ENTRY
    updated = area_registry.async_get_area(area.id)
    assert updated
    assert updated.temperature_entity_id is None


async def test_only_the_deleted_sensor_is_cleared(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a deleted sensor is cleared, and one that may not be up yet stays."""
    area = _kitchen(hass, area_registry, temperature=_TEMPERATURE, humidity=_HUMIDITY)
    _gone(hass, _TEMPERATURE, deleted=False)
    _gone(hass, _HUMIDITY, deleted=True)

    flow = await _flow_for_the_issue(hass, issue_registry, area)
    await flow.async_step_remove()

    assert flow.data
    lines = str(flow.data["entities"]).splitlines()
    assert lines[0].startswith(f"- `{_HUMIDITY}` (deleted on ")
    assert lines[1] == f"- `{_TEMPERATURE}`"
    updated = area_registry.async_get_area(area.id)
    assert updated
    assert updated.temperature_entity_id == _TEMPERATURE
    assert updated.humidity_entity_id is None


async def test_a_sensor_home_assistant_forgot_deleting_stays(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the proof is asked for again when the button is pressed."""
    area = _kitchen(hass, area_registry, temperature=_TEMPERATURE)
    _gone(hass, _TEMPERATURE, deleted=True)
    flow = await _flow_for_the_issue(hass, issue_registry, area)

    async_forget_deleted_entities(hass, freezer)
    result = await flow.async_step_remove()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "changed"
    updated = area_registry.async_get_area(area.id)
    assert updated
    assert updated.temperature_entity_id == _TEMPERATURE
