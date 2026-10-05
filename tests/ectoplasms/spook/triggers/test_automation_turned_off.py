"""Tests for the spook.automation_turned_off trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import Context
from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.ectoplasms.spook.triggers.automation_turned_off import (
    SpookTrigger,
)
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

LIGHTS = "automation.lights"


async def _attach(
    hass: HomeAssistant, target: dict | None = None
) -> tuple[list[tuple[dict, Context | None]], Callable[[], None]]:
    """Attach the trigger, and record everything it hands over."""
    config = await SpookTrigger.async_validate_config(
        hass, {} if target is None else {"target": target}
    )
    handed: list[tuple[dict, Context | None]] = []
    trigger = SpookTrigger(
        hass,
        TriggerConfig(
            key="automation_turned_off",
            target=config.get("target"),
            options=config["options"],
        ),
    )

    def _run(payload, _description, context=None) -> None:  # noqa: ANN001
        handed.append((payload, context))

    unsub = await trigger.async_attach_runner(_run)
    return handed, unsub


def _fired_for(handed: list[tuple[dict, Context | None]]) -> list[str]:
    """Return the automations it fired for, in order."""
    return [payload["entity_id"] for payload, _context in handed]


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "automation_turned_off" in await async_get_triggers(hass)


@pytest.mark.parametrize("config", [{}, {"target": {}}, {"target": None}])
async def test_no_target_means_every_automation(
    hass: HomeAssistant, config: dict
) -> None:
    """Leaving the target out, or empty as the editor does, watches them all."""
    validated = await SpookTrigger.async_validate_config(hass, config)

    assert validated.get("target") is None


async def test_turning_an_automation_off_fires(hass: HomeAssistant) -> None:
    """The point of the whole thing."""
    hass.states.async_set(LIGHTS, STATE_ON)
    handed, unsub = await _attach(hass)

    hass.states.async_set(LIGHTS, STATE_OFF)
    await hass.async_block_till_done()

    unsub()

    assert _fired_for(handed) == [LIGHTS]
    payload, _context = handed[0]
    assert payload["from_state"].state == STATE_ON
    assert payload["to_state"].state == STATE_OFF


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (STATE_OFF, STATE_ON),
        (STATE_UNAVAILABLE, STATE_OFF),
        (STATE_ON, STATE_UNAVAILABLE),
        (STATE_OFF, STATE_OFF),
    ],
)
async def test_only_on_to_off_counts(
    hass: HomeAssistant, before: str, after: str
) -> None:
    """An automation that was not on was not turned off."""
    hass.states.async_set(LIGHTS, before)
    handed, unsub = await _attach(hass)

    hass.states.async_set(LIGHTS, after, {"changed": True})
    await hass.async_block_till_done()

    unsub()

    assert handed == []


async def test_one_that_starts_out_off_was_never_turned_off(
    hass: HomeAssistant,
) -> None:
    """An automation added in the off state has no on it came from."""
    handed, unsub = await _attach(hass)

    hass.states.async_set(LIGHTS, STATE_OFF)
    await hass.async_block_till_done()

    unsub()

    assert handed == []


async def test_a_switch_turned_off_is_not_an_automation(hass: HomeAssistant) -> None:
    """Watching every automation is not watching everything."""
    hass.states.async_set("switch.kettle", STATE_ON)
    handed, unsub = await _attach(hass)

    hass.states.async_set("switch.kettle", STATE_OFF)
    await hass.async_block_till_done()

    unsub()

    assert handed == []


async def test_a_target_narrows_it_down(hass: HomeAssistant) -> None:
    """With a target, only the automations it names count."""
    hass.states.async_set(LIGHTS, STATE_ON)
    hass.states.async_set("automation.heating", STATE_ON)
    handed, unsub = await _attach(hass, {"entity_id": LIGHTS})

    hass.states.async_set("automation.heating", STATE_OFF)
    hass.states.async_set(LIGHTS, STATE_OFF)
    await hass.async_block_till_done()

    unsub()

    assert _fired_for(handed) == [LIGHTS]


async def test_an_area_covers_its_automations_only(
    hass: HomeAssistant,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """An area holds all sorts, and only an automation is turned off here."""
    area = area_registry.async_create("Attic")
    automation = entity_registry.async_get_or_create("automation", "demo", "fan")
    switch = entity_registry.async_get_or_create("switch", "demo", "fan")
    elsewhere = entity_registry.async_get_or_create("automation", "demo", "else")
    for entry in (automation, switch):
        entity_registry.async_update_entity(entry.entity_id, area_id=area.id)
    for entry in (automation, switch, elsewhere):
        hass.states.async_set(entry.entity_id, STATE_ON)

    handed, unsub = await _attach(hass, {"area_id": area.id})

    for entry in (switch, elsewhere, automation):
        hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()

    unsub()

    assert _fired_for(handed) == [automation.entity_id]


async def test_an_automation_moved_into_the_area_is_watched(
    hass: HomeAssistant,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """The target follows the registry, so a later addition counts too."""
    area = area_registry.async_create("Attic")
    automation = entity_registry.async_get_or_create("automation", "demo", "fan")
    hass.states.async_set(automation.entity_id, STATE_ON)
    handed, unsub = await _attach(hass, {"area_id": area.id})

    entity_registry.async_update_entity(automation.entity_id, area_id=area.id)
    await hass.async_block_till_done()
    hass.states.async_set(automation.entity_id, STATE_OFF)
    await hass.async_block_till_done()

    unsub()

    assert _fired_for(handed) == [automation.entity_id]


async def test_it_carries_whoever_turned_it_off(hass: HomeAssistant) -> None:
    """The person is on the context, for Spook's own context conditions."""
    hass.states.async_set(LIGHTS, STATE_ON)
    handed, unsub = await _attach(hass)

    theirs = Context(user_id="abc123")
    hass.states.async_set(LIGHTS, STATE_OFF, context=theirs)
    await hass.async_block_till_done()

    unsub()

    _payload, context = handed[0]
    assert context is theirs


async def test_a_real_automation_turned_off_and_reloaded(hass: HomeAssistant) -> None:
    """Turning one off fires, reloading the lot does not.

    A reload takes every automation away and puts it back, which never
    writes an off. Reading it as one would report every automation in the
    house on every save in the editor.
    """
    config = {
        "automation": [
            {
                "alias": "lights",
                "trigger": {"platform": "event", "event_type": "nothing"},
                "action": [],
            }
        ]
    }
    assert await async_setup_component(hass, "automation", config)
    await hass.async_block_till_done()
    handed, unsub = await _attach(hass)

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call("automation", "reload", blocking=True)
    await hass.async_block_till_done()
    assert handed == []

    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": LIGHTS}, blocking=True
    )
    await hass.async_block_till_done()

    unsub()

    assert _fired_for(handed) == [LIGHTS]


async def test_detaching_stops_it(hass: HomeAssistant) -> None:
    """Nothing is reported once the trigger is detached."""
    hass.states.async_set(LIGHTS, STATE_ON)
    handed, unsub = await _attach(hass, {"entity_id": LIGHTS})
    unsub()

    hass.states.async_set(LIGHTS, STATE_OFF)
    await hass.async_block_till_done()

    assert handed == []
