"""Tests for the spook.update_installed trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.const import EntityCategory
from homeassistant.core import Context, CoreState
from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.update_installed import (
    SpookTrigger,
)
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

FIRMWARE = "update.plug_firmware"


def _on(installed: str, latest: str | None = None) -> dict:
    """Return the attributes of an update entity on a version."""
    return {"installed_version": installed, "latest_version": latest or installed}


async def _automation(hass: HomeAssistant, target: dict) -> list[dict]:
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
                    "alias": "installed",
                    "trigger": {"platform": "spook.update_installed", "target": target},
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "entity_id": "{{ trigger.entity_id }}",
                                "from_version": "{{ trigger.from_version }}",
                                "to_version": "{{ trigger.to_version }}",
                            },
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def _detach(hass: HomeAssistant) -> None:
    """Turn the automation off, which detaches its trigger.

    The harness fails a test that leaves a listener behind, so this doubles
    as a check that the trigger clears up after itself.
    """
    await hass.services.async_call(
        "automation",
        "turn_off",
        {"entity_id": "automation.installed"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "update_installed" in await async_get_triggers(hass)


async def test_a_target_is_required(hass: HomeAssistant) -> None:
    """Without a target there is nothing to watch."""
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(hass, {})


@pytest.mark.parametrize("target", [{}, {"entity_id": []}, {"area_id": None}])
async def test_a_target_that_names_nothing_is_refused(
    hass: HomeAssistant,
    target: dict,
) -> None:
    """An empty target would load and then watch nothing at all."""
    with pytest.raises(vol.Invalid, match="must name at least one"):
        await SpookTrigger.async_validate_config(hass, {"target": target})


async def test_a_new_installed_version_fires(hass: HomeAssistant) -> None:
    """The point of the whole thing."""
    hass.states.async_set(FIRMWARE, STATE_ON, _on("1.0.0", "1.1.0"))
    ran = await _automation(hass, {"entity_id": FIRMWARE})

    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.1.0"))
    await hass.async_block_till_done()

    assert ran == [
        {"entity_id": FIRMWARE, "from_version": "1.0.0", "to_version": "1.1.0"}
    ]

    await _detach(hass)


async def test_an_update_becoming_available_is_not_an_install(
    hass: HomeAssistant,
) -> None:
    """Only the installed version counts, not the one on offer."""
    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.0.0"))
    ran = await _automation(hass, {"entity_id": FIRMWARE})

    hass.states.async_set(FIRMWARE, STATE_ON, _on("1.0.0", "1.1.0"))
    await hass.async_block_till_done()
    hass.states.async_set(
        FIRMWARE, STATE_ON, {**_on("1.0.0", "1.1.0"), "in_progress": True}
    )
    await hass.async_block_till_done()

    assert ran == []

    await _detach(hass)


async def test_a_reboot_into_new_firmware_is_an_install(
    hass: HomeAssistant,
) -> None:
    """The device goes away mid-install and comes back on the new version.

    Unavailable carries no attributes, so comparing a change only with the
    state just before it would never see this one.
    """
    hass.states.async_set(FIRMWARE, STATE_ON, _on("1.0.0", "1.1.0"))
    ran = await _automation(hass, {"entity_id": FIRMWARE})

    hass.states.async_set(FIRMWARE, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.1.0"))
    await hass.async_block_till_done()

    assert ran == [
        {"entity_id": FIRMWARE, "from_version": "1.0.0", "to_version": "1.1.0"}
    ]

    await _detach(hass)


async def test_coming_back_on_the_same_version_is_not_an_install(
    hass: HomeAssistant,
) -> None:
    """A device that drops off the network has not updated anything."""
    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.0.0"))
    ran = await _automation(hass, {"entity_id": FIRMWARE})

    hass.states.async_set(FIRMWARE, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.0.0"))
    await hass.async_block_till_done()

    assert ran == []

    await _detach(hass)


async def test_a_version_reported_late_is_not_an_install(
    hass: HomeAssistant,
) -> None:
    """An entity that only learns its version later started on it."""
    hass.states.async_set(FIRMWARE, STATE_OFF, {"installed_version": None})
    ran = await _automation(hass, {"entity_id": FIRMWARE})

    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.0.0"))
    await hass.async_block_till_done()

    assert ran == []

    # From there on, a change is a change.
    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.1.0"))
    await hass.async_block_till_done()

    assert len(ran) == 1

    await _detach(hass)


async def test_a_rollback_is_a_change_too(hass: HomeAssistant) -> None:
    """Going back a version is installing one, as far as the device goes."""
    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.1.0"))
    ran = await _automation(hass, {"entity_id": FIRMWARE})

    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.0.0"))
    await hass.async_block_till_done()

    assert ran == [
        {"entity_id": FIRMWARE, "from_version": "1.1.0", "to_version": "1.0.0"}
    ]

    await _detach(hass)


async def test_a_start_is_not_a_house_full_of_installs(hass: HomeAssistant) -> None:
    """Nothing is remembered until Home Assistant is up.

    Integrations fill in their versions as they set up, some first from what
    they restored and then from the device. None of that is an install.
    """
    hass.set_state(CoreState.starting)
    hass.states.async_set(FIRMWARE, STATE_OFF, _on("0.0.0"))
    ran = await _automation(hass, {"entity_id": FIRMWARE})

    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.0.0"))
    await hass.async_block_till_done()

    assert ran == []

    # Once the house is up, the version it is on now is the starting point.
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.1.0"))
    await hass.async_block_till_done()

    assert ran == [
        {"entity_id": FIRMWARE, "from_version": "1.0.0", "to_version": "1.1.0"}
    ]

    await _detach(hass)


async def test_a_removed_entity_starts_over(hass: HomeAssistant) -> None:
    """A new entity under the same name has installed nothing yet."""
    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.0.0"))
    ran = await _automation(hass, {"entity_id": FIRMWARE})

    hass.states.async_remove(FIRMWARE)
    await hass.async_block_till_done()
    hass.states.async_set(FIRMWARE, STATE_OFF, _on("2.0.0"))
    await hass.async_block_till_done()

    assert ran == []

    await _detach(hass)


async def test_only_update_entities_in_an_area_are_watched(
    hass: HomeAssistant,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """An area holds all sorts, and only an update entity installs anything.

    A sensor that happens to carry an `installed_version` attribute is not
    an update, whatever it calls its attributes.
    """
    area = area_registry.async_create("Attic")
    update = entity_registry.async_get_or_create("update", "demo", "firmware")
    sensor = entity_registry.async_get_or_create("sensor", "demo", "lookalike")
    for entry in (update, sensor):
        entity_registry.async_update_entity(entry.entity_id, area_id=area.id)
        hass.states.async_set(entry.entity_id, STATE_OFF, _on("1.0.0"))

    ran = await _automation(hass, {"area_id": area.id})

    hass.states.async_set(sensor.entity_id, STATE_OFF, _on("1.1.0"))
    hass.states.async_set(update.entity_id, STATE_OFF, _on("1.1.0"))
    await hass.async_block_till_done()

    assert [run["entity_id"] for run in ran] == [update.entity_id]

    await _detach(hass)


async def test_an_update_entity_of_a_device_is_watched(
    hass: HomeAssistant,
    area_registry,  # noqa: ANN001
    device_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """Update entities are configuration entities, and those count here.

    A device or area normally leaves configuration entities out of a target.
    Doing that here would leave out nearly every update entity there is.
    """
    entry = MockConfigEntry(domain="demo")
    entry.add_to_hass(hass)
    area = area_registry.async_create("Attic")
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("demo", "plug")}
    )
    device_registry.async_update_device(device.id, area_id=area.id)
    update = entity_registry.async_get_or_create(
        "update",
        "demo",
        "firmware",
        device_id=device.id,
        entity_category=EntityCategory.CONFIG,
    )
    hass.states.async_set(update.entity_id, STATE_OFF, _on("1.0.0"))

    ran = await _automation(hass, {"area_id": area.id})

    hass.states.async_set(update.entity_id, STATE_OFF, _on("1.1.0"))
    await hass.async_block_till_done()

    assert [run["entity_id"] for run in ran] == [update.entity_id]

    await _detach(hass)


async def test_the_install_carries_its_own_context(hass: HomeAssistant) -> None:
    """Whoever pressed install is still on it.

    Spook's own context conditions read the person off the state change that
    set the trigger off. A fresh context would make an install somebody asked
    for read as nobody's doing.
    """
    hass.states.async_set(FIRMWARE, STATE_ON, _on("1.0.0", "1.1.0"))

    handed: list[tuple[dict, Context | None]] = []
    trigger = SpookTrigger(
        hass,
        TriggerConfig(
            key="update_installed", target={"entity_id": FIRMWARE}, options={}
        ),
    )

    def _run(payload, _description, context=None) -> None:  # noqa: ANN001
        handed.append((payload, context))

    unsub = await trigger.async_attach_runner(_run)

    theirs = Context(user_id="abc123")
    hass.states.async_set(FIRMWARE, STATE_OFF, _on("1.1.0"), context=theirs)
    await hass.async_block_till_done()

    unsub()

    assert len(handed) == 1
    payload, context = handed[0]
    assert context is theirs
    assert payload["from_state"].attributes["installed_version"] == "1.0.0"
    assert payload["to_state"].attributes["installed_version"] == "1.1.0"
