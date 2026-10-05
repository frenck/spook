"""Tests for the spook.script_started trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.const import STATE_ON
from homeassistant.core import Context
from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.spook.ectoplasms.spook.triggers.script_started import (
    SpookTrigger,
)
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

# Each script waits for the `go` event, so it is still running when the next
# one is asked for.
_WAITS = [{"wait_for_trigger": {"platform": "event", "event_type": "go"}}]


def _scripts(**modes: str) -> dict:
    """Return a script configuration, one waiting script per mode given."""
    return {
        "script": {
            name: {"mode": mode, "sequence": _WAITS} for name, mode in modes.items()
        }
    }


async def _set_up(hass: HomeAssistant, **modes: str) -> dict:
    """Set up the scripts."""
    config = _scripts(**modes)
    assert await async_setup_component(hass, "script", config)
    await hass.async_block_till_done()
    return config


async def _start(
    hass: HomeAssistant, entity_id: str, context: Context | None = None
) -> None:
    """Start a run of a script, without waiting for it to finish.

    `script.turn_on` returns once the run is on the books, which is when the
    state is written. Waiting for everything to settle would wait for the run
    itself, and that waits for `go`.
    """
    await hass.services.async_call(
        "script", "turn_on", {"entity_id": entity_id}, blocking=True, context=context
    )


async def _stop(hass: HomeAssistant) -> None:
    """Stop every run, the queued ones included."""
    await hass.services.async_call(
        "script", "turn_off", {"entity_id": "all"}, blocking=True
    )
    await hass.async_block_till_done()


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
            key="script_started",
            target=config.get("target"),
            options=config["options"],
        ),
    )

    def _run(payload, _description, context=None) -> None:  # noqa: ANN001
        handed.append((payload, context))

    unsub = await trigger.async_attach_runner(_run)
    return handed, unsub


def _fired_for(handed: list[tuple[dict, Context | None]]) -> list[str]:
    """Return the scripts it fired for, in order."""
    return [payload["entity_id"] for payload, _context in handed]


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "script_started" in await async_get_triggers(hass)


@pytest.mark.parametrize("config", [{}, {"target": {}}, {"target": None}])
async def test_no_target_means_every_script(hass: HomeAssistant, config: dict) -> None:
    """Leaving the target out, or empty as the editor does, watches them all."""
    validated = await SpookTrigger.async_validate_config(hass, config)

    assert validated.get("target") is None


async def test_a_run_starting_fires(hass: HomeAssistant) -> None:
    """The point of the whole thing."""
    await _set_up(hass, kettle="single")
    handed, unsub = await _attach(hass)

    await _start(hass, "script.kettle")

    assert _fired_for(handed) == ["script.kettle"]
    payload, _context = handed[0]
    assert payload["to_state"].state == STATE_ON

    # Finishing is not starting.
    hass.bus.async_fire("go")
    await hass.async_block_till_done()
    unsub()

    assert len(handed) == 1


async def test_a_refused_run_does_not_fire(hass: HomeAssistant) -> None:
    """A second run of a script that may only run once never starts.

    Home Assistant's own event fires for it all the same.
    """
    await _set_up(hass, kettle="single")
    handed, unsub = await _attach(hass)
    announced = async_capture_events(hass, "script_started")

    await _start(hass, "script.kettle")
    # Performed as its own action, which comes straight back when refused.
    await hass.services.async_call("script", "kettle", blocking=True)
    await _stop(hass)
    unsub()

    assert [event.data["entity_id"] for event in announced] == ["script.kettle"] * 2
    assert _fired_for(handed) == ["script.kettle"]


@pytest.mark.parametrize("mode", ["parallel", "restart", "queued"])
async def test_every_run_let_through_fires(hass: HomeAssistant, mode: str) -> None:
    """A run that is let through counts, alongside, instead of, or after another.

    A queued one counts when it joins the queue: that is when Home Assistant
    lets it through, and it starts once the one before it is done.
    """
    await _set_up(hass, kettle=mode)
    handed, unsub = await _attach(hass)

    await _start(hass, "script.kettle")
    await _start(hass, "script.kettle")
    await _stop(hass)
    unsub()

    assert _fired_for(handed) == ["script.kettle", "script.kettle"]


async def test_a_reload_is_not_a_start(hass: HomeAssistant) -> None:
    """Reloading takes every script away and puts it back, already stamped."""
    config = await _set_up(hass, kettle="single")
    await _start(hass, "script.kettle")
    await _stop(hass)
    handed, unsub = await _attach(hass)

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call("script", "reload", blocking=True)
    await hass.async_block_till_done()
    unsub()

    assert handed == []


async def test_a_script_that_comes_in_already_stamped_did_not_start(
    hass: HomeAssistant,
) -> None:
    """A script added at a start brings the stamp of its last run along.

    It has no state before it, so there is nothing it changed from.
    """
    handed, unsub = await _attach(hass)

    hass.states.async_set("script.kettle", "off", {"last_triggered": "earlier"})
    await hass.async_block_till_done()
    unsub()

    assert handed == []


async def test_an_automation_running_is_not_a_script(hass: HomeAssistant) -> None:
    """Automations stamp a `last_triggered` of their own on every run."""
    hass.states.async_set("automation.lights", "on", {"last_triggered": "before"})
    handed, unsub = await _attach(hass)

    hass.states.async_set("automation.lights", "on", {"last_triggered": "now"})
    await hass.async_block_till_done()
    unsub()

    assert handed == []


async def test_a_target_narrows_it_down(hass: HomeAssistant) -> None:
    """With a target, only the scripts it names count."""
    await _set_up(hass, kettle="single", toaster="single")
    handed, unsub = await _attach(hass, {"entity_id": "script.kettle"})

    await _start(hass, "script.toaster")
    await _start(hass, "script.kettle")
    await _stop(hass)
    unsub()

    assert _fired_for(handed) == ["script.kettle"]


async def test_an_area_covers_its_scripts(
    hass: HomeAssistant,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """A script in the area counts, one elsewhere does not."""
    await _set_up(hass, kettle="single", toaster="single")
    area = area_registry.async_create("Kitchen")
    entity_registry.async_update_entity("script.kettle", area_id=area.id)
    handed, unsub = await _attach(hass, {"area_id": area.id})

    await _start(hass, "script.toaster")
    await _start(hass, "script.kettle")
    await _stop(hass)
    unsub()

    assert _fired_for(handed) == ["script.kettle"]


async def test_it_carries_whoever_started_it(hass: HomeAssistant) -> None:
    """The person is on the context, for Spook's own context conditions."""
    await _set_up(hass, kettle="single")
    handed, unsub = await _attach(hass)

    theirs = Context(user_id="abc123")
    await _start(hass, "script.kettle", context=theirs)
    await _stop(hass)
    unsub()

    _payload, context = handed[0]
    assert context is not None
    assert context.id == theirs.id


async def test_detaching_stops_it(hass: HomeAssistant) -> None:
    """Nothing is reported once the trigger is detached."""
    await _set_up(hass, kettle="single")
    handed, unsub = await _attach(hass, {"entity_id": "script.kettle"})
    unsub()

    await _start(hass, "script.kettle")
    await _stop(hass)

    assert handed == []
