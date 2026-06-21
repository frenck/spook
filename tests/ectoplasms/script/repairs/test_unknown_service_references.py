"""Tests for script unknown service reference repairs."""

# pylint: disable=protected-access

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

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
