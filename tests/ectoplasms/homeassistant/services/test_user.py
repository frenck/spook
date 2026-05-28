"""Tests for the homeassistant enable_user and disable_user services."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.spook.ectoplasms.homeassistant.services import (
    disable_user,
    enable_user,
)

if TYPE_CHECKING:
    from homeassistant.auth.models import User

    from tests.common import MockUser


@pytest.fixture
def user_services(hass: HomeAssistant) -> None:
    """Register the Spook user services."""
    hass.config.components.add(DOMAIN)
    enable_user.SpookService(hass).async_register()
    disable_user.SpookService(hass).async_register()


@pytest.mark.usefixtures("user_services")
async def test_disable_user_service_disables_user(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test the disable user service disables a user."""
    user = await hass.auth.async_create_user("Target User")

    assert user.is_active

    await hass.services.async_call(
        DOMAIN,
        "disable_user",
        {"user_id": user.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert not user.is_active


@pytest.mark.usefixtures("user_services")
async def test_enable_user_service_enables_user(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test the enable user service enables a user."""
    user = await hass.auth.async_create_user("Target User")
    await hass.auth.async_update_user(user, is_active=False)

    assert not user.is_active

    await hass.services.async_call(
        DOMAIN,
        "enable_user",
        {"user_id": user.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert user.is_active


@pytest.mark.usefixtures("user_services")
async def test_user_services_accept_multiple_users(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test the user services accept multiple user IDs."""
    users = [
        await hass.auth.async_create_user("First User"),
        await hass.auth.async_create_user("Second User"),
    ]

    await hass.services.async_call(
        DOMAIN,
        "disable_user",
        {"user_id": [user.id for user in users]},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert all(not user.is_active for user in users)

    await hass.services.async_call(
        DOMAIN,
        "enable_user",
        {"user_id": [user.id for user in users]},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert all(user.is_active for user in users)


@pytest.mark.parametrize(
    ("service", "message"),
    [
        ("disable_user", "Could not find user: missing-user"),
        ("enable_user", "Could not find user: missing-user"),
    ],
)
@pytest.mark.usefixtures("user_services")
async def test_user_services_raise_on_missing_user(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    service: str,
    message: str,
) -> None:
    """Test the user services raise when the user does not exist."""
    with pytest.raises(HomeAssistantError, match=re.escape(message)):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"user_id": "missing-user"},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )


@pytest.mark.parametrize(
    ("service", "message"),
    [
        ("disable_user", "Cannot disable a system-generated user"),
        ("enable_user", "Cannot enable a system-generated user"),
    ],
)
@pytest.mark.usefixtures("user_services")
async def test_user_services_raise_on_system_generated_user(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    service: str,
    message: str,
) -> None:
    """Test the user services raise when the user is system-generated."""
    user: User = await hass.auth.async_create_system_user("System User")

    with pytest.raises(HomeAssistantError, match=re.escape(message)):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"user_id": user.id},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
