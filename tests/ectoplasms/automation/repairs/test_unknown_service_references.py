"""Tests for automation unknown service reference repairs."""

# pylint: disable=protected-access

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.automation.repairs.unknown_service_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant

# Shaped after two blueprints in the wild: each calls the integration an
# input picks in a branch of its own, and nobody has all of them.
SEVERAL_INTEGRATIONS_BLUEPRINT = """
blueprint:
  name: Notify me
  domain: automation
  input:
    source:
      default: nordpool
variables:
  source: !input source
triggers:
  - trigger: event
    event_type: arrived
actions:
  - choose:
      - conditions: "{{ source == 'tibber' }}"
        sequence:
          - action: tibber.get_prices
      - conditions: "{{ source == 'telegram' }}"
        sequence:
          - action: telegram_bot.send_photo
  - action: light.turn_onn
"""


def test_automation_unknown_service_repair_inspects_when_components_load() -> None:
    """Test automation service references are rechecked when components load."""
    assert EVENT_COMPONENT_LOADED in SpookRepair.inspect_events


async def _unknown_in_automation(
    hass: HomeAssistant, actions: list[dict[str, Any]]
) -> set[str]:
    """Set up a real automation and ask the repair about it."""
    hass.services.async_register("light", "turn_on", lambda _call: None)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "garage",
                "alias": "garage",
                "triggers": [{"trigger": "event", "event_type": "arrived"}],
                "actions": actions,
            }
        },
    )
    await hass.async_block_till_done()

    entity = hass.data["automation"].get_entity("automation.garage")
    repair = SpookRepair(hass)
    await repair._async_setup_inspection()  # noqa: SLF001
    return await repair._async_compute_unknown_references(entity)  # noqa: SLF001


async def test_actions_in_a_sequence_block_are_checked(hass: HomeAssistant) -> None:
    """The editor's "sequence" building block runs its steps like any other."""
    actions = [
        {
            "sequence": [
                {"action": "light.turn_on"},
                {"delay": 0},
                {"action": "cover.xopen_garage"},
                {"sequence": [{"action": "light.xdeeper"}]},
            ]
        }
    ]

    assert await _unknown_in_automation(hass, actions) == {
        "cover.xopen_garage",
        "light.xdeeper",
    }


async def test_a_parked_sequence_block_and_its_data_are_left_alone(
    hass: HomeAssistant,
) -> None:
    """A disabled block runs nothing, and a `sequence` in data is no step."""
    actions = [
        {"enabled": False, "sequence": [{"action": "cover.xparked_block"}]},
        {
            "sequence": [
                {"enabled": False, "action": "cover.xparked_step"},
                {
                    "action": "light.turn_on",
                    "data": {"sequence": [{"action": "cover.xjust_data"}]},
                },
            ]
        },
    ]

    assert await _unknown_in_automation(hass, actions) == set()


async def test_a_blueprint_for_integrations_that_are_not_there(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test a blueprint's actions of integrations that are not loaded are left out.

    Whoever uses the blueprint cannot edit the branches for integrations
    they do not have, and those never run. A missing action of a loaded
    integration is still reported. #2068, #2019.
    """
    hass.config.config_dir = str(tmp_path)
    blueprint = tmp_path / "blueprints" / "automation" / "frenck" / "notify.yaml"
    blueprint.parent.mkdir(parents=True)
    blueprint.write_text(SEVERAL_INTEGRATIONS_BLUEPRINT, encoding="utf-8")
    hass.config.components.add("light")

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "garage",
                "alias": "garage",
                "use_blueprint": {"path": "frenck/notify.yaml"},
            }
        },
    )
    await hass.async_block_till_done()

    entity = hass.data["automation"].get_entity("automation.garage")
    assert entity.referenced_blueprint == "frenck/notify.yaml"
    repair = SpookRepair(hass)
    await repair._async_setup_inspection()  # noqa: SLF001

    assert await repair._async_compute_unknown_references(entity) == {  # noqa: SLF001
        "light.turn_onn"
    }


async def test_written_by_hand_the_same_actions_are_reported(
    hass: HomeAssistant,
) -> None:
    """Test an automation somebody wrote themselves is judged in full."""
    hass.config.components.add("light")
    actions = [
        {
            "choose": [
                {
                    "conditions": "{{ source == 'tibber' }}",
                    "sequence": [{"action": "tibber.get_prices"}],
                }
            ]
        },
        {"action": "telegram_bot.send_photo"},
        {"action": "light.turn_onn"},
    ]

    assert await _unknown_in_automation(hass, actions) == {
        "tibber.get_prices",
        "telegram_bot.send_photo",
        "light.turn_onn",
    }
