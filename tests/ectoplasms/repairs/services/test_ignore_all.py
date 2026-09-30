"""Tests for the repairs.ignore_all and repairs.unignore_all services."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from homeassistant.components.repairs import DOMAIN
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.repairs.services import (
    ignore_all,
    unignore_all,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from tests.common import MockUser


@pytest.fixture(autouse=True)
async def _repairs(hass: HomeAssistant) -> None:
    """Raise two issues, and register both actions."""
    assert await async_setup_component(hass, DOMAIN, {})
    for issue_id in ("first", "second"):
        ir.async_create_issue(
            hass,
            "hue",
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=issue_id,
        )
    ignore_all.SpookService(hass).async_register()
    unignore_all.SpookService(hass).async_register()


def _ignored(hass: HomeAssistant) -> set[str]:
    """Return the IDs of the issues that are ignored."""
    return {
        issue.issue_id
        for issue in ir.async_get(hass).issues.values()
        if issue.dismissed_version is not None
    }


async def test_an_admin_can_ignore_and_unignore_everything(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Both do what they say, for everything raised."""
    context = Context(user_id=hass_admin_user.id)

    await hass.services.async_call(
        DOMAIN, "ignore_all", {}, blocking=True, context=context
    )
    assert _ignored(hass) == {"first", "second"}

    await hass.services.async_call(
        DOMAIN, "unignore_all", {}, blocking=True, context=context
    )
    assert _ignored(hass) == set()


async def test_an_automation_can_still_use_them(hass: HomeAssistant) -> None:
    """Automations and scripts run without a user, and are not refused."""
    await hass.services.async_call(DOMAIN, "ignore_all", {}, blocking=True)

    assert _ignored(hass) == {"first", "second"}


@pytest.mark.parametrize("service", ["ignore_all", "unignore_all"])
async def test_only_an_admin_can_change_what_everybody_sees(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    service: str,
) -> None:
    """Ignoring hides an issue for every user, so it takes an admin."""
    ir.async_ignore_issue(hass, "hue", "second", ignore=True)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            service,
            {},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    assert _ignored(hass) == {"second"}
