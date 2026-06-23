"""Tests for the sensor set_display_precision service."""

from __future__ import annotations

from re import escape
from typing import TYPE_CHECKING

import pytest

from homeassistant.components.sensor import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.spook.ectoplasms.sensor.services import set_display_precision

DISPLAY_PRECISION = 3

if TYPE_CHECKING:
    from homeassistant.helpers import entity_registry as er

    from tests.common import MockUser


@pytest.fixture
async def sensor_set_display_precision_service(hass: HomeAssistant) -> None:
    """Register the set display precision service."""
    hass.config.components.add(DOMAIN)
    set_display_precision.SpookService(hass).async_register()


@pytest.mark.usefixtures("sensor_set_display_precision_service")
async def test_set_display_precision_updates_sensor_options(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_admin_user: MockUser,
) -> None:
    """Test the service stores the display precision in entity options."""
    entity_registry.async_get_or_create(
        DOMAIN, "test", "unique-id", suggested_object_id="test"
    )

    await hass.services.async_call(
        DOMAIN,
        "set_display_precision",
        {ATTR_ENTITY_ID: "sensor.test", "display_precision": DISPLAY_PRECISION},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    entry = entity_registry.async_get("sensor.test")
    assert entry is not None
    assert entry.options[DOMAIN]["display_precision"] == DISPLAY_PRECISION


@pytest.mark.usefixtures("sensor_set_display_precision_service")
async def test_set_display_precision_rejects_unknown_sensor(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test the service rejects unknown sensor entities."""
    with pytest.raises(
        HomeAssistantError, match=escape("Unknown sensor entity: sensor.missing")
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_display_precision",
            {ATTR_ENTITY_ID: "sensor.missing", "display_precision": DISPLAY_PRECISION},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
