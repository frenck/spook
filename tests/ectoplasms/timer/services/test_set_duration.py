"""Tests for the timer.set_duration service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.components.timer import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.timer.services import set_duration

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from tests.common import MockUser

_TEN_MINUTES = {"minutes": 10}


@pytest.fixture(autouse=True)
async def _timer(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up one timer made in the UI, and the Spook action."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "data": {"items": [{"id": "mist", "name": "Mist", "duration": "0:05:00"}]},
    }
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    set_duration.SpookService(hass).async_register()


async def _set_duration(hass: HomeAssistant, context: Context | None = None) -> None:
    """Ask for the timer to take ten minutes from now on."""
    await hass.services.async_call(
        DOMAIN,
        "set_duration",
        {ATTR_ENTITY_ID: "timer.mist", "duration": _TEN_MINUTES},
        blocking=True,
        context=context,
    )


async def test_an_admin_can_change_how_long_it_takes(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """The change lands on the stored timer."""
    await _set_duration(hass, Context(user_id=hass_admin_user.id))
    await hass.async_block_till_done()

    assert hass.states.get("timer.mist").attributes["duration"] == "0:10:00"


async def test_an_automation_can_change_how_long_it_takes(
    hass: HomeAssistant,
) -> None:
    """Without a user behind the call, nothing stands in the way."""
    await _set_duration(hass)
    await hass.async_block_till_done()

    assert hass.states.get("timer.mist").attributes["duration"] == "0:10:00"


async def test_somebody_who_is_not_an_admin_cannot(
    hass: HomeAssistant,
    hass_owner_user: MockUser,
) -> None:
    """Changing a timer as it is stored is configuration, like the UI keeps it.

    Starting or pausing a timer is using it. This changes it for good, which
    editing it in the UI only lets an admin do. Somebody who may switch the
    timer on and off is not refused for that reason, so the refusal is this.
    """
    # Somebody else owns the house, or the first user made becomes its owner.
    assert hass_owner_user.is_owner
    user = await hass.auth.async_create_user(
        "Allowed to use it", group_ids=[GROUP_ID_USER]
    )
    assert not user.is_admin

    with pytest.raises(Unauthorized):
        await _set_duration(hass, Context(user_id=user.id))

    assert hass.states.get("timer.mist").attributes["duration"] == "0:05:00"


async def test_it_registers_on_a_core_without_admin_only(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The oldest Home Assistant Spook runs on cannot be asked for an admin.

    Its entity actions take no `admin_only`, and handing it one fails the
    registration of every action built this way, not only this one.
    """
    registered: list[str] = []

    def _without_admin_only(
        _self: EntityComponent,
        name: str,
        schema: Any,
        func: Any,
        required_features: Any = None,
        supports_response: Any = None,
    ) -> None:
        # Named one by one, like that version's, so anything more fails.
        del schema, func, required_features, supports_response
        registered.append(name)

    monkeypatch.setattr(
        EntityComponent, "async_register_entity_service", _without_admin_only
    )

    assert set_duration.SpookService(hass).async_register()
    assert registered == ["set_duration"]
