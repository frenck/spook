"""Tests for the input_number.set_range action."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.components.input_number import DOMAIN
from homeassistant.core import Context
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.input_number.services import set_range

if TYPE_CHECKING:
    from tests.common import MockUser

    from homeassistant.core import HomeAssistant

SLIDER = "input_number.track_position"


@pytest.fixture(autouse=True)
async def _numbers(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up one input number made in the UI, one from YAML, and the action."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "minor_version": 1,
        "data": {
            "items": [
                {
                    "id": "track_position",
                    "name": "Track position",
                    "min": 0,
                    "max": 10000,
                    "step": 1,
                    "mode": "slider",
                }
            ]
        },
    }
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"from_yaml": {"min": 0, "max": 10}}}
    )
    await hass.async_block_till_done()
    set_range.SpookService(hass).async_register()


async def _set_range(hass: HomeAssistant, entity_id: str = SLIDER, **data: Any) -> None:
    """Perform the action, the way an automation does."""
    await hass.services.async_call(
        DOMAIN, "set_range", {"entity_id": entity_id, **data}, blocking=True
    )
    await hass.async_block_till_done()


async def test_the_range_follows_what_it_measures(hass: HomeAssistant) -> None:
    """Discussion #1134: a slider that fits the length of the track loaded."""
    await _set_range(hass, max=1834)

    attributes = hass.states.get(SLIDER).attributes
    assert (attributes["min"], attributes["max"], attributes["step"]) == (0, 1834, 1)


async def test_min_max_and_step_can_change_together(hass: HomeAssistant) -> None:
    """Everything given changes, in one go."""
    await _set_range(hass, min=10, max=20, step=0.5)

    attributes = hass.states.get(SLIDER).attributes
    assert (attributes["min"], attributes["max"], attributes["step"]) == (10, 20, 0.5)


async def test_a_value_outside_the_new_range_is_moved_inside(
    hass: HomeAssistant,
) -> None:
    """Home Assistant moves the value into the new range itself."""
    await hass.services.async_call(
        DOMAIN, "set_value", {"entity_id": SLIDER, "value": 5000}, blocking=True
    )

    await _set_range(hass, max=1834)

    assert float(hass.states.get(SLIDER).state) == 1834  # noqa: PLR2004


async def test_a_maximum_not_above_the_minimum_is_refused(
    hass: HomeAssistant,
) -> None:
    """Home Assistant's own check, refused with nothing stored."""
    with pytest.raises(ServiceValidationError, match="not greater than"):
        await _set_range(hass, max=0)

    assert hass.states.get(SLIDER).attributes["max"] == 10000  # noqa: PLR2004


async def test_asking_for_nothing_is_refused(hass: HomeAssistant) -> None:
    """Neither a minimum, a maximum nor a step: there is nothing to change."""
    with pytest.raises(ServiceValidationError, match="Give a minimum"):
        await _set_range(hass)


async def test_one_from_yaml_is_refused(hass: HomeAssistant) -> None:
    """Only a helper made in the UI is stored where this can change it."""
    with pytest.raises(HomeAssistantError, match="not editable"):
        await _set_range(hass, entity_id="input_number.from_yaml", max=5)


async def test_somebody_who_is_not_an_admin_cannot(
    hass: HomeAssistant, hass_owner_user: MockUser
) -> None:
    """Changing how the helper is set up is configuration, kept to admins.

    Somebody allowed to use the slider is not refused for that reason, so the
    refusal is this.
    """
    # Somebody else owns the house, or the first user made becomes its owner.
    assert hass_owner_user.is_owner
    user = await hass.auth.async_create_user(
        "Allowed to use it", group_ids=[GROUP_ID_USER]
    )
    assert not user.is_admin

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "set_range",
            {"entity_id": SLIDER, "max": 5},
            blocking=True,
            context=Context(user_id=user.id),
        )

    assert hass.states.get(SLIDER).attributes["max"] == 10000  # noqa: PLR2004
