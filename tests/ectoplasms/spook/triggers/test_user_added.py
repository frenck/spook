"""Tests for the spook.user_added trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
from homeassistant.setup import async_setup_component

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _automation(hass: HomeAssistant) -> list[dict]:
    """Set up an automation on the trigger and record every run."""
    ran: list[dict] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(dict(call.data))

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "new user",
                    "trigger": {"platform": "spook.user_added"},
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "user_id": "{{ trigger.user_id }}",
                                "name": "{{ trigger.name }}",
                                "is_admin": "{{ trigger.is_admin }}",
                            },
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def test_a_new_user_is_reported(hass: HomeAssistant) -> None:
    """Test somebody given a login fires the trigger, with who it is.

    The owner is there first: Home Assistant makes the very first user the
    owner, and an owner is an administrator whatever group it is put in.
    """
    await hass.auth.async_create_user("Owner", group_ids=[GROUP_ID_ADMIN])
    ran = await _automation(hass)

    user = await hass.auth.async_create_user("Mallory", group_ids=[GROUP_ID_USER])
    await hass.async_block_till_done()

    assert ran == [{"user_id": user.id, "name": "Mallory", "is_admin": False}]


async def test_a_new_admin_says_so(hass: HomeAssistant) -> None:
    """Test a user made an administrator is reported as one."""
    await hass.auth.async_create_user("Owner", group_ids=[GROUP_ID_ADMIN])
    ran = await _automation(hass)

    await hass.auth.async_create_user("Trent", group_ids=[GROUP_ID_ADMIN])
    await hass.async_block_till_done()

    assert len(ran) == 1
    assert ran[0]["is_admin"] is True


async def test_a_user_home_assistant_makes_for_itself_is_left_out(
    hass: HomeAssistant,
) -> None:
    """Test a system user, the kind an integration is given, does not fire.

    Nobody can log in as one of those, so it is nobody's news.
    """
    ran = await _automation(hass)

    await hass.auth.async_create_system_user("Supervisor")
    await hass.async_block_till_done()

    assert ran == []
