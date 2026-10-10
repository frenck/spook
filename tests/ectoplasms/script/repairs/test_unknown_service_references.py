"""Tests for script unknown service reference repairs."""

# pylint: disable=protected-access

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.script.repairs.unknown_service_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_script_unknown_service_repair_finds_unknown_actions(
    hass: HomeAssistant,
) -> None:
    """Test script action sequences are inspected for unknown services."""
    repair = SpookRepair(hass)
    repair._known_services = {"light.turn_on"}  # noqa: SLF001
    entity = SimpleNamespace(
        script=SimpleNamespace(
            sequence=[
                {"action": "light.turn_on"},
                {"action": "spook.boo"},
            ]
        )
    )

    assert await repair._async_compute_unknown_references(entity) == {  # noqa: SLF001
        "spook.boo"
    }


async def test_actions_in_a_sequence_block_of_a_script_are_checked(
    hass: HomeAssistant,
) -> None:
    """A real script with a "sequence" building block has its steps checked."""
    hass.services.async_register("light", "turn_on", lambda _call: None)
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "garage": {
                    "sequence": [
                        {
                            "sequence": [
                                {"action": "light.turn_on"},
                                {"action": "cover.xopen_garage"},
                                {"enabled": False, "action": "cover.xparked"},
                            ]
                        }
                    ]
                }
            }
        },
    )
    await hass.async_block_till_done()

    entity = hass.data["script"].get_entity("script.garage")
    repair = SpookRepair(hass)
    await repair._async_setup_inspection()  # noqa: SLF001

    assert await repair._async_compute_unknown_references(entity) == {  # noqa: SLF001
        "cover.xopen_garage"
    }
