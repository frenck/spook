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
    from pathlib import Path

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


async def test_a_blueprint_for_integrations_that_are_not_there(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test a blueprint's actions of integrations that are not loaded are left out.

    Whoever uses the blueprint cannot edit the branches for integrations
    they do not have. A missing action of a loaded integration is still
    reported, and so is all of it in a script somebody wrote themselves.
    #2068, #2019.
    """
    hass.config.config_dir = str(tmp_path)
    blueprint = tmp_path / "blueprints" / "script" / "frenck" / "notify.yaml"
    blueprint.parent.mkdir(parents=True)
    blueprint.write_text(
        """
blueprint:
  name: Notify me
  domain: script
sequence:
  - action: telegram_bot.send_photo
  - action: light.turn_onn
""",
        encoding="utf-8",
    )
    hass.config.components.add("light")

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "blueprinted": {"use_blueprint": {"path": "frenck/notify.yaml"}},
                "handwritten": {
                    "sequence": [
                        {"action": "telegram_bot.send_photo"},
                        {"action": "light.turn_onn"},
                    ]
                },
            }
        },
    )
    await hass.async_block_till_done()

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()  # noqa: SLF001

    async def _unknown(script_id: str) -> set[str]:
        entity = hass.data["script"].get_entity(f"script.{script_id}")
        return await repair._async_compute_unknown_references(entity)  # noqa: SLF001

    assert await _unknown("blueprinted") == {"light.turn_onn"}
    assert await _unknown("handwritten") == {
        "telegram_bot.send_photo",
        "light.turn_onn",
    }
