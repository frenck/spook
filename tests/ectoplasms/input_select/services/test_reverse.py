"""Tests for the input_select.reverse action."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.input_select import DOMAIN
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.input_select.services import reverse

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_the_options_are_turned_around(hass: HomeAssistant) -> None:
    """Discussion #1032: a history that grows at the end, newest on top.

    Back to front, not sorted, and the selected option stays selected.
    """
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "history": {
                    "options": ["first song", "a second one", "the newest"],
                    "initial": "a second one",
                }
            }
        },
    )
    await hass.async_block_till_done()
    reverse.SpookService(hass).async_register()

    await hass.services.async_call(
        DOMAIN, "reverse", {"entity_id": "input_select.history"}, blocking=True
    )

    state = hass.states.get("input_select.history")
    assert state.attributes["options"] == ["the newest", "a second one", "first song"]
    assert state.state == "a second one"
