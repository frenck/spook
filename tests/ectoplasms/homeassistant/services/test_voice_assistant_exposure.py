"""Tests for the homeassistant expose_entity and unexpose_entity services."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.components.homeassistant.exposed_entities import (
    async_get_entity_settings,
    async_should_expose,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.homeassistant.services import (
    expose_entity,
    unexpose_entity,
)

if TYPE_CHECKING:
    from tests.common import MockUser

_ASSIST = "conversation"
_ALEXA = "cloud.alexa"
_GOOGLE = "cloud.google_assistant"


@pytest.fixture
async def exposure_services(hass: HomeAssistant) -> None:
    """Register the Spook exposure services."""
    # The exposure settings live in the homeassistant integration's storage.
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    expose_entity.SpookService(hass).async_register()
    unexpose_entity.SpookService(hass).async_register()


@pytest.fixture
def light(hass: HomeAssistant) -> str:
    """Return a registered light entity."""
    return (
        er.async_get(hass)
        .async_get_or_create("light", "test", "lamp", suggested_object_id="lamp")
        .entity_id
    )


async def _call(
    hass: HomeAssistant,
    user: MockUser,
    service: str,
    entity_id: str | list[str],
    assistants: list[str],
) -> None:
    """Call one of the exposure services as an admin."""
    await hass.services.async_call(
        DOMAIN,
        service,
        {"entity_id": entity_id, "assistants": assistants},
        blocking=True,
        context=Context(user_id=user.id),
    )


@pytest.mark.usefixtures("exposure_services")
async def test_expose_sets_exposure_for_the_named_assistant(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    light: str,
) -> None:
    """Test exposing to one assistant leaves the others alone."""
    await _call(hass, hass_admin_user, "expose_entity", light, [_ASSIST])

    assert async_should_expose(hass, _ASSIST, light) is True
    # Untouched assistants keep whatever default they had.
    assert _ALEXA not in async_get_entity_settings(hass, light)


@pytest.mark.usefixtures("exposure_services")
async def test_expose_accepts_several_assistants(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    light: str,
) -> None:
    """Test every named assistant is set."""
    await _call(
        hass, hass_admin_user, "expose_entity", light, [_ASSIST, _ALEXA, _GOOGLE]
    )

    assert all(
        async_should_expose(hass, assistant, light) is True
        for assistant in (_ASSIST, _ALEXA, _GOOGLE)
    )


@pytest.mark.usefixtures("exposure_services")
async def test_unexpose_turns_it_back_off(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    light: str,
) -> None:
    """Test the exposure is removed again."""
    await _call(hass, hass_admin_user, "expose_entity", light, [_ASSIST])
    assert async_should_expose(hass, _ASSIST, light) is True

    await _call(hass, hass_admin_user, "unexpose_entity", light, [_ASSIST])

    assert async_should_expose(hass, _ASSIST, light) is False


@pytest.mark.usefixtures("exposure_services")
async def test_an_unknown_entity_changes_nothing(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    light: str,
) -> None:
    """Test one bad entity leaves the good ones untouched.

    Checking while applying would expose the entities listed ahead of the
    bad one and then raise, with nothing saying which got through.
    """
    with pytest.raises(HomeAssistantError, match=re.escape("light.nope")):
        await _call(
            hass, hass_admin_user, "expose_entity", [light, "light.nope"], [_ASSIST]
        )

    assert _ASSIST not in async_get_entity_settings(hass, light)


@pytest.mark.usefixtures("exposure_services")
async def test_an_unknown_assistant_is_refused(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    light: str,
) -> None:
    """Test only assistants Home Assistant knows about are accepted."""
    with pytest.raises(vol.Invalid):
        await _call(hass, hass_admin_user, "expose_entity", light, ["cloud.siri"])
