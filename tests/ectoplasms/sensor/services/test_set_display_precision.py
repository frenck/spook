"""Tests for the sensor set_display_precision service."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.spook.ectoplasms.sensor.services import set_display_precision

if TYPE_CHECKING:
    from tests.common import MockUser

_PRECISION = 2
_OTHER_PRECISION = 3


@pytest.fixture
def display_precision_service(hass: HomeAssistant) -> None:
    """Register the Spook set_display_precision service."""
    hass.config.components.add(DOMAIN)
    set_display_precision.SpookService(hass).async_register()


@pytest.fixture
def sensors(hass: HomeAssistant) -> list[str]:
    """Return two registered sensor entities."""
    entity_registry = er.async_get(hass)
    return [
        entity_registry.async_get_or_create(
            DOMAIN, "test", unique_id, suggested_object_id=unique_id
        ).entity_id
        for unique_id in ("power", "energy")
    ]


def _precision(hass: HomeAssistant, entity_id: str) -> int | None:
    """Return the stored display precision for an entity."""
    entry = er.async_get(hass).async_get(entity_id)
    return entry.options.get(DOMAIN, {}).get("display_precision")


async def _call(
    hass: HomeAssistant,
    user: MockUser,
    entity_id: str | list[str],
    precision: int,
) -> None:
    """Call the service as an admin."""
    await hass.services.async_call(
        DOMAIN,
        "set_display_precision",
        {"entity_id": entity_id, "display_precision": precision},
        blocking=True,
        context=Context(user_id=user.id),
    )


@pytest.mark.usefixtures("display_precision_service")
async def test_sets_the_display_precision(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    sensors: list[str],
) -> None:
    """Test the display precision is stored on the entity."""
    assert _precision(hass, sensors[0]) is None

    await _call(hass, hass_admin_user, sensors[0], _PRECISION)

    assert _precision(hass, sensors[0]) == _PRECISION


@pytest.mark.usefixtures("display_precision_service")
async def test_zero_decimals_is_a_valid_choice(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    sensors: list[str],
) -> None:
    """Test asking for no decimals is stored rather than treated as unset."""
    await _call(hass, hass_admin_user, sensors[0], 0)

    assert _precision(hass, sensors[0]) == 0


@pytest.mark.usefixtures("display_precision_service")
async def test_applies_to_every_entity_given(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    sensors: list[str],
) -> None:
    """Test a list of sensors is all updated."""
    await _call(hass, hass_admin_user, sensors, _OTHER_PRECISION)

    assert all(_precision(hass, entity_id) == _OTHER_PRECISION for entity_id in sensors)


@pytest.mark.usefixtures("display_precision_service")
async def test_other_sensor_options_survive(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    sensors: list[str],
) -> None:
    """Test an existing sensor option is not dropped.

    The options are stored as one mapping per domain, so writing the whole
    thing back would take a custom unit with it.
    """
    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity_options(
        sensors[0], DOMAIN, {"unit_of_measurement": "kW"}
    )

    await _call(hass, hass_admin_user, sensors[0], 1)

    options = entity_registry.async_get(sensors[0]).options[DOMAIN]
    assert options["display_precision"] == 1
    assert options["unit_of_measurement"] == "kW"


@pytest.mark.usefixtures("display_precision_service")
async def test_an_unknown_entity_changes_nothing(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    sensors: list[str],
) -> None:
    """Test one bad entity leaves the good ones untouched.

    Validating while applying would update the sensors listed before the bad
    one and then raise, with nothing telling the user which got through.
    """
    with pytest.raises(HomeAssistantError, match=re.escape("sensor.nope")):
        await _call(hass, hass_admin_user, [sensors[0], "sensor.nope"], 4)

    assert _precision(hass, sensors[0]) is None


@pytest.mark.usefixtures("display_precision_service")
async def test_a_non_sensor_entity_is_refused(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test an entity from another domain is refused."""
    er.async_get(hass).async_get_or_create(
        "light", "test", "lamp", suggested_object_id="lamp"
    )

    with pytest.raises(HomeAssistantError, match=re.escape("light.lamp")):
        await _call(hass, hass_admin_user, "light.lamp", _PRECISION)


@pytest.mark.usefixtures("display_precision_service")
async def test_a_negative_precision_is_refused(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    sensors: list[str],
) -> None:
    """Test a negative number of decimals is rejected by the schema."""
    with pytest.raises(vol.Invalid):
        await _call(hass, hass_admin_user, sensors[0], -1)

    assert _precision(hass, sensors[0]) is None
