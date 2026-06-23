"""Tests for the voice assistant exposure services."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

from re import escape
from typing import TYPE_CHECKING

import pytest

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.components.homeassistant.const import DATA_EXPOSED_ENTITIES
from homeassistant.components.homeassistant.exposed_entities import (
    ExposedEntities,
    async_should_expose,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.spook.ectoplasms.homeassistant.services import (
    expose_entity,
    unexpose_entity,
)

if TYPE_CHECKING:
    from tests.common import MockUser


@pytest.fixture
async def voice_exposed_entities(hass: HomeAssistant) -> None:
    """Set up the exposed entities manager."""
    exposed = ExposedEntities(hass)
    await exposed.async_initialize()
    hass.data[DATA_EXPOSED_ENTITIES] = exposed


@pytest.fixture
async def voice_assistant_exposure_services(
    hass: HomeAssistant,
    voice_exposed_entities: None,
) -> None:
    """Register the voice assistant exposure services."""
    assert voice_exposed_entities is None
    hass.config.components.add(DOMAIN)
    expose_entity.SpookService(hass).async_register()
    unexpose_entity.SpookService(hass).async_register()


@pytest.mark.usefixtures("voice_assistant_exposure_services")
async def test_expose_entity_exposes_to_assistants(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test the expose entity service updates assistant exposure."""
    hass.states.async_set("light.test", "on")

    await hass.services.async_call(
        DOMAIN,
        "expose_entity",
        {
            ATTR_ENTITY_ID: "light.test",
            "assistants": ["conversation", "cloud.google_assistant"],
        },
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert async_should_expose(hass, "conversation", "light.test")
    assert async_should_expose(hass, "cloud.google_assistant", "light.test")


@pytest.mark.usefixtures("voice_assistant_exposure_services")
async def test_unexpose_entity_unexposes_from_assistants(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test the unexpose entity service updates assistant exposure."""
    hass.states.async_set("light.test", "on")
    expose_entity.SpookService(hass)

    await hass.services.async_call(
        DOMAIN,
        "expose_entity",
        {ATTR_ENTITY_ID: "light.test", "assistants": ["conversation"]},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.services.async_call(
        DOMAIN,
        "unexpose_entity",
        {ATTR_ENTITY_ID: "light.test", "assistants": ["conversation"]},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert not async_should_expose(hass, "conversation", "light.test")


@pytest.mark.usefixtures("voice_assistant_exposure_services")
async def test_expose_entity_rejects_unknown_entity(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test the expose entity service rejects unknown entities."""
    with pytest.raises(
        HomeAssistantError, match=escape("Unknown entity: light.missing")
    ):
        await hass.services.async_call(
            DOMAIN,
            "expose_entity",
            {ATTR_ENTITY_ID: "light.missing", "assistants": ["conversation"]},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
