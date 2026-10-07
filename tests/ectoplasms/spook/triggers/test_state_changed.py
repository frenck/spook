"""Tests for spook.state_changed, Spook's state trigger."""

# pylint: disable=wrong-import-order,too-many-lines
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed_exact,
)

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import Context
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.state_changed import (
    SpookTrigger,
)
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        area_registry as ar,
        device_registry as dr,
        entity_registry as er,
        label_registry as lr,
    )

FRONT = "binary_sensor.front_door"
BACK = "binary_sensor.back_door"
LAMP = "light.lamp"

Handed = list[tuple[dict[str, Any], Context | None]]

# Leaves the target out altogether, rather than aiming at the front door.
NO_TARGET: dict[str, Any] = {"no": "target"}


async def _validate(
    hass: HomeAssistant, options: dict[str, Any] | None = None, target: Any = None
) -> dict[str, Any]:
    """Validate a configuration the way an automation would."""
    config: dict[str, Any] = {}
    if target is not NO_TARGET:
        config["target"] = {"entity_id": FRONT} if target is None else target
    if options is not None:
        config["options"] = options
    return await SpookTrigger.async_validate_config(hass, config)


async def _attach(
    hass: HomeAssistant,
    target: dict[str, Any] | None = None,
    **options: Any,
) -> tuple[Handed, Callable[[], None]]:
    """Attach the trigger, and record everything it hands over."""
    validated = await _validate(hass, options, target)
    handed: Handed = []
    trigger = SpookTrigger(
        hass,
        TriggerConfig(
            key="state_changed",
            target=validated.get("target"),
            options=validated["options"],
        ),
    )

    def _run(payload, _description, context=None) -> None:  # noqa: ANN001
        handed.append((payload, context))

    unsub = await trigger.async_attach_runner(_run)
    return handed, unsub


async def _set(
    hass: HomeAssistant,
    entity_id: str,
    state: str,
    attributes: dict[str, Any] | None = None,
    context: Context | None = None,
) -> None:
    """Write a state and let it be handled."""
    hass.states.async_set(entity_id, state, attributes, context=context)
    await hass.async_block_till_done()


async def _later(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Let time pass, and let whatever was due run.

    To the microsecond: the usual helper adds half a second of slack, which
    would let a timer fire before its moment without any test noticing.
    """
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()


def _fired_for(handed: Handed) -> list[str]:
    """Return the entities the trigger fired for, in order."""
    return [payload["entity_id"] for payload, _context in handed]


# Validation


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "state_changed" in await async_get_triggers(hass)


@pytest.mark.parametrize("target", [NO_TARGET, {}, {"entity_id": []}, {"label_id": []}])
async def test_no_target_and_nothing_picked_is_refused(
    hass: HomeAssistant, target: dict[str, Any]
) -> None:
    """Every entity in the house is a mistake, not a setting."""
    with pytest.raises(vol.Invalid, match="Give a target, or pick entities"):
        await _validate(hass, {"exclude_domain": "sensor"}, target)


@pytest.mark.parametrize(
    "picked",
    [
        {"domain": "binary_sensor"},
        {"integration": "zha"},
        {"config_entry": "abc"},
        {"device_class": "door"},
    ],
)
@pytest.mark.parametrize("target", [NO_TARGET, {}, {"entity_id": []}])
async def test_without_a_target_the_lists_pick(
    hass: HomeAssistant, target: dict[str, Any], picked: dict[str, Any]
) -> None:
    """Any one of them is enough, and an empty target is no target."""
    validated = await _validate(hass, picked, target)

    assert validated.get("target") is None


async def test_leaving_out_the_options_takes_the_defaults(hass: HomeAssistant) -> None:
    """A bare target is a working trigger."""
    validated = await _validate(hass)

    assert validated["options"] == {
        "ignore_unavailable": True,
        "attribute_changes": False,
        "behavior": "each",
    }


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"from": ["on"], "not_from": ["off"]}, "either from or not_from"),
        ({"to": ["on"], "not_to": ["off"]}, "either to or not_to"),
        ({"to": [STATE_UNAVAILABLE]}, "to names unavailable"),
        ({"to": [STATE_UNKNOWN]}, "to names unknown"),
        ({"from": [STATE_UNAVAILABLE]}, "from names unavailable"),
        ({"from": ["on", STATE_UNKNOWN]}, "from names unknown"),
        (
            {"to": [STATE_UNAVAILABLE], "ignore_unavailable": True},
            "turn off ignore_unavailable",
        ),
        ({"blip_tolerance": "00:00:30"}, "only means something together with for"),
        ({"behavior": "most"}, "behavior"),
        ({"behavior": "any"}, "behavior"),
        ({"for": "soon"}, "for"),
        ({"delay": -5}, "delay"),
        ({"domain": [{"not": "text"}]}, "domain"),
        ({"exclude_target": {"color": "red"}}, "exclude_target"),
        ({"shout": True}, "shout"),
    ],
)
async def test_options_that_contradict_or_make_no_sense_are_refused(
    hass: HomeAssistant, options: dict[str, Any], message: str
) -> None:
    """Each one would be a trigger that cannot do what it says."""
    with pytest.raises(vol.Invalid, match=message):
        await _validate(hass, options)


@pytest.mark.parametrize(
    "options",
    [
        {"to": [STATE_UNAVAILABLE], "ignore_unavailable": False},
        {"from": [STATE_UNKNOWN], "ignore_unavailable": False},
        {"not_to": [STATE_UNAVAILABLE]},
        {"not_from": [STATE_UNKNOWN, STATE_UNAVAILABLE]},
        {"attribute": "brightness", "attribute_changes": True},
        {"attribute": "brightness", "attribute_changes": False},
        {"attribute": "brightness"},
        {"for": "00:01:00", "blip_tolerance": "00:00:10"},
        {"from": ["off"], "not_to": ["on"]},
        {"to": ["on"], "not_from": ["on"]},
        {"exclude_target": {}},
    ],
)
async def test_options_that_go_together_are_taken(
    hass: HomeAssistant, options: dict[str, Any]
) -> None:
    """Asking for unavailable after switching off the ignoring is fine."""
    await _validate(hass, options)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("on", ["on"]), (255, ["255"]), (True, ["True"]), (["on", 1], ["on", "1"])],
)
async def test_values_become_lists_of_text(
    hass: HomeAssistant, value: Any, expected: list[str]
) -> None:
    """What the editor sends, text, is what everything is compared as."""
    validated = await _validate(hass, {"to": value, "ignore_unavailable": False})

    assert validated["options"]["to"] == expected


@pytest.mark.parametrize("behavior", ["each", "first", "all"])
async def test_the_behaviors_are_taken(hass: HomeAssistant, behavior: str) -> None:
    """The three of Home Assistant's own entity triggers."""
    validated = await _validate(hass, {"behavior": behavior, "to": "on"})

    assert validated["options"]["behavior"] == behavior


@pytest.mark.parametrize("behavior", ["first", "all"])
@pytest.mark.parametrize(
    "options", [{}, {"from": "off"}, {"not_from": "off"}, {"attribute": "x"}]
)
async def test_first_and_all_need_somewhere_to_get_to(
    hass: HomeAssistant, behavior: str, options: dict[str, Any]
) -> None:
    """Without to or not_to every state is already there: a dead trigger."""
    with pytest.raises(vol.Invalid, match="needs to or not_to"):
        await _validate(hass, {"behavior": behavior, **options})


@pytest.mark.parametrize("behavior", ["first", "all"])
@pytest.mark.parametrize("options", [{"to": "on"}, {"not_to": "off"}])
async def test_first_and_all_take_to_or_not_to(
    hass: HomeAssistant, behavior: str, options: dict[str, Any]
) -> None:
    """Either one gives the target somewhere to get to."""
    await _validate(hass, {"behavior": behavior, **options})


async def test_each_needs_nowhere_to_get_to(hass: HomeAssistant) -> None:
    """For each entity on its own, any change is a change."""
    await _validate(hass, {"behavior": "each"})


async def test_first_with_not_to_fires(hass: HomeAssistant) -> None:
    """The first door that is no longer closed."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass, {"entity_id": [FRONT, BACK]}, not_to="off", behavior="first"
    )

    await _set(hass, BACK, "on")
    await _set(hass, FRONT, "on")
    unsub()

    assert _fired_for(handed) == [BACK]


# Which changes


async def test_a_change_of_state_fires(hass: HomeAssistant) -> None:
    """The point of the whole thing."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass)

    await _set(hass, FRONT, "on")
    unsub()

    assert len(handed) == 1
    payload, _context = handed[0]
    assert payload["entity_id"] == FRONT
    assert payload["from_state"].state == "off"
    assert payload["to_state"].state == "on"
    assert payload["for"] is None
    assert payload["delay"] is None


async def test_it_carries_the_context_of_the_change(hass: HomeAssistant) -> None:
    """Whoever changed it is on it, for Spook's own context conditions."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass)

    theirs = Context(user_id="abc123")
    await _set(hass, FRONT, "on", context=theirs)
    unsub()

    assert handed[0][1] is theirs


async def test_an_attribute_change_is_not_a_change(hass: HomeAssistant) -> None:
    """A brightness moving while the lamp stays on is noise, by default."""
    await _set(hass, LAMP, "on", {"brightness": 10})
    handed, unsub = await _attach(hass, {"entity_id": LAMP})

    await _set(hass, LAMP, "on", {"brightness": 200})
    unsub()

    assert handed == []


async def test_attribute_changes_count_when_asked(hass: HomeAssistant) -> None:
    """Turned off, any change at all fires."""
    await _set(hass, LAMP, "on", {"brightness": 10})
    handed, unsub = await _attach(hass, {"entity_id": LAMP}, attribute_changes=True)

    await _set(hass, LAMP, "on", {"brightness": 200})
    await _set(hass, LAMP, "off")
    unsub()

    assert _fired_for(handed) == [LAMP, LAMP]


async def test_nothing_changing_at_all_does_not_fire(hass: HomeAssistant) -> None:
    """Writing the same state again is not a change, even counting attributes."""
    await _set(hass, LAMP, "on", {"brightness": 10})
    handed, unsub = await _attach(hass, {"entity_id": LAMP}, attribute_changes=True)

    hass.states.async_set(LAMP, "on", {"brightness": 10}, force_update=True)
    await hass.async_block_till_done()
    unsub()

    assert handed == []


@pytest.mark.parametrize(
    ("options", "old", "new", "fires"),
    [
        ({}, "off", "on", True),
        ({"to": ["on"]}, "off", "on", True),
        ({"to": ["on"]}, "on", "off", False),
        ({"to": ["on", "open"]}, "closed", "open", True),
        ({"from": ["off"]}, "off", "on", True),
        ({"from": ["off"]}, "on", "off", False),
        ({"from": ["off"], "to": ["on"]}, "off", "on", True),
        ({"from": ["off"], "to": ["on"]}, "idle", "on", False),
        ({"not_to": ["on"]}, "off", "on", False),
        ({"not_to": ["on"]}, "on", "off", True),
        ({"not_from": ["off"]}, "off", "on", False),
        ({"not_from": ["off"]}, "idle", "on", True),
        ({"not_from": ["off"], "not_to": ["idle"]}, "on", "idle", False),
        ({"not_from": ["off"], "to": ["on"]}, "idle", "on", True),
        ({"from": ["off"], "not_to": ["idle"]}, "off", "on", True),
    ],
)
async def test_from_and_to_narrow_it_down(
    hass: HomeAssistant,
    options: dict[str, Any],
    old: str,
    new: str,
    *,
    fires: bool,
) -> None:
    """From, to and their opposites, alone and together."""
    await _set(hass, FRONT, old)
    handed, unsub = await _attach(hass, **options)

    await _set(hass, FRONT, new)
    unsub()

    assert bool(handed) is fires


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("off", STATE_UNAVAILABLE),
        (STATE_UNAVAILABLE, "on"),
        ("off", STATE_UNKNOWN),
        (STATE_UNKNOWN, "on"),
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
    ],
)
async def test_unavailable_and_unknown_are_ignored(
    hass: HomeAssistant, old: str, new: str
) -> None:
    """A router rebooting does not take every door through a change."""
    await _set(hass, FRONT, old)
    handed, unsub = await _attach(hass)

    await _set(hass, FRONT, new)
    unsub()

    assert handed == []


@pytest.mark.parametrize(
    ("old", "new"),
    [("off", STATE_UNAVAILABLE), (STATE_UNAVAILABLE, "on"), (STATE_UNKNOWN, "on")],
)
async def test_unavailable_and_unknown_count_when_asked(
    hass: HomeAssistant, old: str, new: str
) -> None:
    """Switched off, they are states like any other."""
    await _set(hass, FRONT, old)
    handed, unsub = await _attach(hass, ignore_unavailable=False)

    await _set(hass, FRONT, new)
    unsub()

    assert len(handed) == 1


async def test_going_unavailable_can_be_the_trigger(hass: HomeAssistant) -> None:
    """With the ignoring off, unavailable can be asked for by name."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, ignore_unavailable=False, to=[STATE_UNAVAILABLE]
    )

    await _set(hass, FRONT, "on")
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    unsub()

    assert [payload["to_state"].state for payload, _ in handed] == [STATE_UNAVAILABLE]


async def test_not_to_unavailable_is_fine_while_ignoring(hass: HomeAssistant) -> None:
    """Saying the same thing twice is not a contradiction."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, not_to=[STATE_UNAVAILABLE])

    await _set(hass, FRONT, "on")
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    unsub()

    assert len(handed) == 1


async def test_a_restored_state_at_start_is_not_a_change(hass: HomeAssistant) -> None:
    """At a start, an entity not set up yet is restored as unavailable."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass)

    await _set(hass, FRONT, STATE_UNAVAILABLE, {"restored": True})
    await _set(hass, FRONT, "off")
    unsub()

    assert handed == []


async def test_appearing_and_disappearing_are_not_changes(hass: HomeAssistant) -> None:
    """An entity created or removed has no other side to compare with."""
    handed, unsub = await _attach(hass)

    await _set(hass, FRONT, "on")
    hass.states.async_remove(FRONT)
    await hass.async_block_till_done()
    unsub()

    assert handed == []


# Following an attribute


async def test_an_attribute_can_be_followed(hass: HomeAssistant) -> None:
    """The brightness changing is the change, the state staying on is not."""
    await _set(hass, LAMP, "on", {"brightness": 10})
    handed, unsub = await _attach(hass, {"entity_id": LAMP}, attribute="brightness")

    await _set(hass, LAMP, "on", {"brightness": 200})
    await _set(hass, LAMP, "on", {"brightness": 200, "color_mode": "hs"})
    unsub()

    assert len(handed) == 1
    assert handed[0][0]["to_state"].attributes["brightness"] == 200  # noqa: PLR2004


@pytest.mark.parametrize("counts", [True, False])
async def test_attribute_changes_add_nothing_to_an_attribute(
    hass: HomeAssistant, *, counts: bool
) -> None:
    """Following an attribute, only that attribute changing counts, either way."""
    await _set(hass, LAMP, "on", {"brightness": 10, "color_mode": "hs"})
    handed, unsub = await _attach(
        hass,
        {"entity_id": LAMP},
        attribute="brightness",
        attribute_changes=counts,
    )

    await _set(hass, LAMP, "on", {"brightness": 10, "color_mode": "xy"})
    await _set(hass, LAMP, "on", {"brightness": 200, "color_mode": "xy"})
    unsub()

    assert len(handed) == 1


async def test_a_state_change_is_not_an_attribute_change(hass: HomeAssistant) -> None:
    """Following an attribute, the state itself does not matter."""
    await _set(hass, LAMP, "on", {"brightness": 10})
    handed, unsub = await _attach(hass, {"entity_id": LAMP}, attribute="brightness")

    await _set(hass, LAMP, "off", {"brightness": 10})
    unsub()

    assert handed == []


async def test_attribute_values_are_compared_as_text(hass: HomeAssistant) -> None:
    """A brightness of 255 is the "255" typed into the editor."""
    await _set(hass, LAMP, "on", {"brightness": 10})
    handed, unsub = await _attach(
        hass, {"entity_id": LAMP}, attribute="brightness", to="255"
    )

    await _set(hass, LAMP, "on", {"brightness": 128})
    await _set(hass, LAMP, "on", {"brightness": 255})
    unsub()

    assert len(handed) == 1


async def test_an_attribute_showing_up_is_a_change(hass: HomeAssistant) -> None:
    """From nothing to something, unless a value was asked for."""
    await _set(hass, LAMP, "off")
    handed, unsub = await _attach(hass, {"entity_id": LAMP}, attribute="brightness")

    await _set(hass, LAMP, "on", {"brightness": 10})
    unsub()

    assert len(handed) == 1


async def test_a_missing_attribute_is_not_a_value_asked_for(
    hass: HomeAssistant,
) -> None:
    """Gone is not any value somebody could have typed."""
    await _set(hass, LAMP, "on", {"brightness": 10})
    handed, unsub = await _attach(
        hass, {"entity_id": LAMP}, attribute="brightness", not_to=["10"]
    )

    await _set(hass, LAMP, "on", {"brightness": 20})
    await _set(hass, LAMP, "off")
    unsub()

    assert len(handed) == 2  # noqa: PLR2004
    assert "brightness" not in handed[1][0]["to_state"].attributes


async def test_an_attribute_of_an_unavailable_entity_is_ignored(
    hass: HomeAssistant,
) -> None:
    """The ignoring is about the entity, whatever is being followed."""
    await _set(hass, LAMP, "on", {"brightness": 10})
    handed, unsub = await _attach(hass, {"entity_id": LAMP}, attribute="brightness")

    await _set(hass, LAMP, STATE_UNAVAILABLE)
    await _set(hass, LAMP, "on", {"brightness": 10})
    unsub()

    assert handed == []


# Which entities


async def test_a_label_covers_everything_with_it(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Including what gets the label after the trigger loaded."""
    label = label_registry.async_create("Outside door")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    back = entity_registry.async_get_or_create("binary_sensor", "demo", "back")
    entity_registry.async_update_entity(front.entity_id, labels={label.label_id})
    for entry in (front, back):
        await _set(hass, entry.entity_id, "off")

    handed, unsub = await _attach(hass, {"label_id": label.label_id})

    await _set(hass, back.entity_id, "on")
    entity_registry.async_update_entity(back.entity_id, labels={label.label_id})
    await hass.async_block_till_done()
    await _set(hass, back.entity_id, "off")
    await _set(hass, front.entity_id, "on")
    unsub()

    assert _fired_for(handed) == [back.entity_id, front.entity_id]


async def test_an_entity_losing_the_label_drops_out(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """The target is followed both ways."""
    label = label_registry.async_create("Outside door")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    entity_registry.async_update_entity(front.entity_id, labels={label.label_id})
    await _set(hass, front.entity_id, "off")

    handed, unsub = await _attach(hass, {"label_id": label.label_id})

    entity_registry.async_update_entity(front.entity_id, labels=set())
    await hass.async_block_till_done()
    await _set(hass, front.entity_id, "on")
    unsub()

    assert handed == []


def _device_in_area(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    area_name: str = "Hallway",
) -> tuple[str, str, MockConfigEntry]:
    """Return a device in an area, its area, and its config entry."""
    entry = MockConfigEntry(domain="demo")
    entry.add_to_hass(hass)
    area = area_registry.async_get_or_create(area_name)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("demo", area_name)}
    )
    device_registry.async_update_device(device.id, area_id=area.id)
    return device.id, area.id, entry


async def test_through_an_area_only_primary_entities_count(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The battery and signal sensors of a door are not the door."""
    device_id, area_id, entry = _device_in_area(hass, device_registry, area_registry)
    door = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "door", device_id=device_id, config_entry=entry
    )
    signal = entity_registry.async_get_or_create(
        "sensor",
        "demo",
        "signal",
        device_id=device_id,
        config_entry=entry,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    await _set(hass, door.entity_id, "off")
    await _set(hass, signal.entity_id, "-70")

    handed, unsub = await _attach(hass, {"area_id": area_id})

    await _set(hass, signal.entity_id, "-60")
    await _set(hass, door.entity_id, "on")
    unsub()

    assert _fired_for(handed) == [door.entity_id]


async def test_a_diagnostic_entity_named_directly_counts(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Named on purpose is wanted on purpose."""
    signal = entity_registry.async_get_or_create(
        "sensor", "demo", "signal", entity_category=EntityCategory.DIAGNOSTIC
    )
    await _set(hass, signal.entity_id, "-70")
    handed, unsub = await _attach(hass, {"entity_id": signal.entity_id})

    await _set(hass, signal.entity_id, "-60")
    unsub()

    assert len(handed) == 1


@pytest.fixture(name="mixed")
def fixture_mixed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> dict[str, str]:
    """Return a label on a bit of everything, from two integrations and entries."""
    label = label_registry.async_create("Everything")
    zha = MockConfigEntry(domain="zha", entry_id="zha_entry")
    hue = MockConfigEntry(domain="hue", entry_id="hue_entry")
    zha.add_to_hass(hass)
    hue.add_to_hass(hass)

    made = {
        "door": entity_registry.async_get_or_create(
            "binary_sensor",
            "zha",
            "door",
            config_entry=zha,
            original_device_class="door",
        ),
        "window": entity_registry.async_get_or_create(
            "binary_sensor",
            "zha",
            "window",
            config_entry=zha,
            original_device_class="window",
        ),
        "motion": entity_registry.async_get_or_create(
            "binary_sensor",
            "hue",
            "motion",
            config_entry=hue,
            original_device_class="motion",
        ),
        "lamp": entity_registry.async_get_or_create(
            "light", "hue", "lamp", config_entry=hue
        ),
        "plug": entity_registry.async_get_or_create(
            "switch", "zha", "plug", config_entry=zha, original_device_class="outlet"
        ),
    }
    for entry in made.values():
        entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})
        hass.states.async_set(entry.entity_id, "off")

    ids = {name: entry.entity_id for name, entry in made.items()}
    ids["label"] = label.label_id
    return ids


async def _flip_all(hass: HomeAssistant, mixed: dict[str, str]) -> None:
    """Turn on everything the mixed label covers, in a fixed order."""
    for name in ("door", "window", "motion", "lamp", "plug"):
        await _set(hass, mixed[name], "on")


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, ["door", "window", "motion", "lamp", "plug"]),
        ({"domain": ["binary_sensor"]}, ["door", "window", "motion"]),
        ({"domain": ["light", "switch"]}, ["lamp", "plug"]),
        ({"integration": ["hue"]}, ["motion", "lamp"]),
        ({"config_entry": ["zha_entry"]}, ["door", "window", "plug"]),
        ({"device_class": ["door", "window"]}, ["door", "window"]),
        ({"domain": ["binary_sensor"], "integration": ["zha"]}, ["door", "window"]),
        (
            {
                "domain": ["binary_sensor"],
                "integration": ["zha"],
                "device_class": ["window"],
            },
            ["window"],
        ),
        ({"domain": ["light"], "integration": ["zha"]}, []),
        ({"exclude_domain": ["binary_sensor"]}, ["lamp", "plug"]),
        ({"exclude_integration": ["zha"]}, ["motion", "lamp"]),
        ({"exclude_config_entry": ["hue_entry"]}, ["door", "window", "plug"]),
        ({"exclude_device_class": ["motion", "outlet"]}, ["door", "window", "lamp"]),
        (
            {"exclude_domain": ["binary_sensor"], "exclude_integration": ["hue"]},
            ["door", "window", "lamp", "plug"],
        ),
        (
            {"domain": ["binary_sensor"], "exclude_device_class": ["motion"]},
            ["door", "window"],
        ),
        ({"integration": ["zha"], "exclude_domain": ["switch"]}, ["door", "window"]),
    ],
)
async def test_filters_narrow_the_target_down(
    hass: HomeAssistant,
    mixed: dict[str, str],
    options: dict[str, Any],
    expected: list[str],
) -> None:
    """Any match within a list, all lists together, and the same to leave out."""
    handed, unsub = await _attach(hass, {"label_id": mixed["label"]}, **options)

    await _flip_all(hass, mixed)
    unsub()

    assert _fired_for(handed) == [mixed[name] for name in expected]


async def test_an_exclude_target_is_taken_out(
    hass: HomeAssistant, mixed: dict[str, str]
) -> None:
    """Everything minus the bits named."""
    handed, unsub = await _attach(
        hass,
        {"label_id": mixed["label"]},
        exclude_target={"entity_id": [mixed["door"], mixed["lamp"]]},
    )

    await _flip_all(hass, mixed)
    unsub()

    assert _fired_for(handed) == [mixed["window"], mixed["motion"], mixed["plug"]]


async def test_exclude_filters_narrow_the_exclude_target(
    hass: HomeAssistant, mixed: dict[str, str]
) -> None:
    """Leaving out the zha part of what is named, not all of it."""
    handed, unsub = await _attach(
        hass,
        {"label_id": mixed["label"]},
        exclude_target={"entity_id": [mixed["door"], mixed["lamp"]]},
        exclude_integration=["zha"],
    )

    await _flip_all(hass, mixed)
    unsub()

    assert _fired_for(handed) == [
        mixed["window"],
        mixed["motion"],
        mixed["lamp"],
        mixed["plug"],
    ]


async def test_an_exclude_target_outside_the_target_changes_nothing(
    hass: HomeAssistant, mixed: dict[str, str]
) -> None:
    """Leaving out what was never in does not take anything else with it."""
    handed, unsub = await _attach(
        hass, {"entity_id": mixed["door"]}, exclude_target={"entity_id": LAMP}
    )

    await _flip_all(hass, mixed)
    unsub()

    assert _fired_for(handed) == [mixed["door"]]


async def test_excluding_an_area_takes_its_diagnostic_entities_too(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Leaving out too much does no harm, too little does."""
    device_id, area_id, entry = _device_in_area(hass, device_registry, area_registry)
    signal = entity_registry.async_get_or_create(
        "sensor",
        "demo",
        "signal",
        device_id=device_id,
        config_entry=entry,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    await _set(hass, signal.entity_id, "-70")
    handed, unsub = await _attach(
        hass, {"entity_id": signal.entity_id}, exclude_target={"area_id": area_id}
    )

    await _set(hass, signal.entity_id, "-60")
    unsub()

    assert handed == []


async def test_an_entity_moving_into_an_excluded_area_drops_out(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The exclude side is followed as it changes too."""
    garage = area_registry.async_get_or_create("Garage")
    door = entity_registry.async_get_or_create("binary_sensor", "demo", "door")
    await _set(hass, door.entity_id, "off")
    handed, unsub = await _attach(
        hass, {"entity_id": door.entity_id}, exclude_target={"area_id": garage.id}
    )

    entity_registry.async_update_entity(door.entity_id, area_id=garage.id)
    await hass.async_block_till_done()
    await _set(hass, door.entity_id, "on")
    unsub()

    assert handed == []


async def test_device_class_set_by_the_user_wins(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Showing a window sensor as a door makes it a door."""
    sensor = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "contact", original_device_class="window"
    )
    entity_registry.async_update_entity(sensor.entity_id, device_class="door")
    await _set(hass, sensor.entity_id, "off")
    handed, unsub = await _attach(
        hass, {"entity_id": sensor.entity_id}, device_class=["door"]
    )

    await _set(hass, sensor.entity_id, "on")
    unsub()

    assert len(handed) == 1


async def test_without_a_registry_entry_the_state_does_not_tell_the_device_class(
    hass: HomeAssistant,
) -> None:
    """A filter only reads the registry, which is what it hears changing.

    Reading the state would be a filter that looks once, at load, and keeps
    a door that has since become a window.
    """
    await _set(hass, FRONT, "off", {"device_class": "door"})
    handed, unsub = await _attach(hass, device_class=["door"])

    await _set(hass, FRONT, "on", {"device_class": "door"})
    unsub()

    assert handed == []


@pytest.mark.parametrize(
    "options",
    [
        {"integration": ["demo"]},
        {"config_entry": ["anything"]},
        {"device_class": ["door"]},
    ],
)
async def test_without_a_registry_entry_there_is_nothing_to_match(
    hass: HomeAssistant, options: dict[str, Any]
) -> None:
    """No integration or entry to name, and no device class in its state."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, **options)

    await _set(hass, FRONT, "on")
    unsub()

    assert handed == []


@pytest.mark.parametrize(
    "options",
    [{"exclude_integration": ["demo"]}, {"exclude_config_entry": ["anything"]}],
)
async def test_without_a_registry_entry_nothing_is_left_out_either(
    hass: HomeAssistant, options: dict[str, Any]
) -> None:
    """A filter that cannot match keeps nothing, and leaves nothing out."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, **options)

    await _set(hass, FRONT, "on")
    unsub()

    assert len(handed) == 1


async def test_filters_that_leave_nothing_still_load(hass: HomeAssistant) -> None:
    """The target can still grow into them, so it is not refused."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, domain=["cover"])

    await _set(hass, FRONT, "on")
    unsub()

    assert handed == []


# Picking without a target


async def test_without_a_target_device_class_picks_from_everything(
    hass: HomeAssistant, mixed: dict[str, str]
) -> None:
    """Every door in the house, without a label on any of them."""
    handed, unsub = await _attach(hass, NO_TARGET, device_class=["door", "window"])

    await _flip_all(hass, mixed)
    unsub()

    assert _fired_for(handed) == [mixed["door"], mixed["window"]]


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({"domain": ["light", "switch"]}, ["lamp", "plug"]),
        ({"integration": ["hue"]}, ["motion", "lamp"]),
        ({"config_entry": ["zha_entry"]}, ["door", "window", "plug"]),
        ({"integration": ["zha"], "exclude_domain": ["switch"]}, ["door", "window"]),
    ],
)
async def test_without_a_target_every_list_picks(
    hass: HomeAssistant,
    mixed: dict[str, str],
    options: dict[str, Any],
    expected: list[str],
) -> None:
    """Domain, integration and entry pick the same way, and leaving out works."""
    handed, unsub = await _attach(hass, NO_TARGET, **options)

    await _flip_all(hass, mixed)
    unsub()

    assert _fired_for(handed) == [mixed[name] for name in expected]


async def test_picking_keeps_to_primary_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Like a target through a device: a diagnostic door is not a door."""
    primary = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "door", original_device_class="door"
    )
    diagnostic = entity_registry.async_get_or_create(
        "binary_sensor",
        "demo",
        "tamper",
        original_device_class="door",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    for entry in (primary, diagnostic):
        await _set(hass, entry.entity_id, "off")
    handed, unsub = await _attach(hass, NO_TARGET, device_class=["door"])

    await _set(hass, diagnostic.entity_id, "on")
    await _set(hass, primary.entity_id, "on")
    unsub()

    assert _fired_for(handed) == [primary.entity_id]


async def test_picking_by_domain_finds_entities_without_a_registry_entry(
    hass: HomeAssistant,
) -> None:
    """Only a domain can pick those, as they have nothing else to go on."""
    await _set(hass, FRONT, "off", {"device_class": "door"})
    by_domain, unsub_domain = await _attach(hass, NO_TARGET, domain="binary_sensor")
    by_class, unsub_class = await _attach(hass, NO_TARGET, device_class="door")

    await _set(hass, FRONT, "on", {"device_class": "door"})
    unsub_domain()
    unsub_class()

    assert _fired_for(by_domain) == [FRONT]
    assert by_class == []


async def test_a_new_entity_is_picked_up_as_it_arrives(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """A door added after the trigger loaded joins straight away."""
    handed, unsub = await _attach(hass, NO_TARGET, device_class=["door"])

    door = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "new_door", original_device_class="door"
    )
    await hass.async_block_till_done()
    await _set(hass, door.entity_id, "off")
    await _set(hass, door.entity_id, "on")
    unsub()

    assert [p["to_state"].state for p, _ in handed] == ["on"]


async def test_picking_with_a_leave_out_target(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Every door, except the ones in the garage."""
    garage = area_registry.async_get_or_create("Garage")
    front = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "front", original_device_class="door"
    )
    shed = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "garage", original_device_class="door"
    )
    entity_registry.async_update_entity(shed.entity_id, area_id=garage.id)
    for entry in (front, shed):
        await _set(hass, entry.entity_id, "off")
    handed, unsub = await _attach(
        hass, NO_TARGET, device_class="door", exclude_target={"area_id": garage.id}
    )

    await _set(hass, shed.entity_id, "on")
    await _set(hass, front.entity_id, "on")
    unsub()

    assert _fired_for(handed) == [front.entity_id]


# Behavior


async def test_each_fires_for_every_entity(hass: HomeAssistant) -> None:
    """Every door on its own."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(hass, {"entity_id": [FRONT, BACK]}, to="on")

    await _set(hass, FRONT, "on")
    await _set(hass, BACK, "on")
    unsub()

    assert _fired_for(handed) == [FRONT, BACK]


async def test_first_fires_for_the_first_one_only(hass: HomeAssistant) -> None:
    """And again once none of them are, and one is."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass, {"entity_id": [FRONT, BACK]}, to="on", behavior="first"
    )

    await _set(hass, FRONT, "on")
    await _set(hass, BACK, "on")
    await _set(hass, FRONT, "off")
    await _set(hass, FRONT, "on")
    await _set(hass, FRONT, "off")
    await _set(hass, BACK, "off")
    await _set(hass, BACK, "on")
    unsub()

    assert _fired_for(handed) == [FRONT, BACK]


async def test_all_fires_when_the_last_one_gets_there(hass: HomeAssistant) -> None:
    """Not a moment before."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass, {"entity_id": [FRONT, BACK]}, to="off", behavior="all"
    )

    await _set(hass, FRONT, "on")
    await _set(hass, BACK, "on")
    await _set(hass, FRONT, "off")
    assert handed == []

    await _set(hass, BACK, "off")
    unsub()

    assert _fired_for(handed) == [BACK]


async def test_all_leaves_out_what_is_unavailable(hass: HomeAssistant) -> None:
    """A door that is not answering is neither open nor closed."""
    await _set(hass, FRONT, "on")
    await _set(hass, BACK, STATE_UNAVAILABLE)
    handed, unsub = await _attach(
        hass, {"entity_id": [FRONT, BACK]}, to="off", behavior="all"
    )

    await _set(hass, FRONT, "off")
    unsub()

    assert _fired_for(handed) == [FRONT]


async def test_all_waits_for_the_unavailable_when_they_count(
    hass: HomeAssistant,
) -> None:
    """With the ignoring off, unavailable is a state that is not closed."""
    await _set(hass, FRONT, "on")
    await _set(hass, BACK, STATE_UNAVAILABLE)
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="off",
        behavior="all",
        ignore_unavailable=False,
    )

    await _set(hass, FRONT, "off")
    assert handed == []

    await _set(hass, BACK, "off")
    unsub()

    assert _fired_for(handed) == [BACK]


@pytest.mark.parametrize("behavior", ["first", "all"])
async def test_staying_there_is_not_getting_there(
    hass: HomeAssistant, behavior: str
) -> None:
    """An attribute change of one that is already there moves no count."""
    await _set(hass, LAMP, "on", {"brightness": 10})
    handed, unsub = await _attach(
        hass,
        {"entity_id": LAMP},
        to="on",
        behavior=behavior,
        attribute_changes=True,
    )

    await _set(hass, LAMP, "on", {"brightness": 20})
    unsub()

    assert handed == []


# For


async def test_for_waits_until_it_held(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Open for five minutes, not for four."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, to="on", **{"for": "00:05:00"})

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 240)
    assert handed == []

    await _later(hass, freezer, 61)
    unsub()

    assert len(handed) == 1
    assert handed[0][0]["for"] == timedelta(minutes=5)
    assert handed[0][0]["to_state"].state == "on"


async def test_for_is_called_off_by_a_change(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Closed again in between, so it did not hold."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, to="on", **{"for": "00:05:00"})

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 120)
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_for_starts_over_on_a_new_change(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Every change that qualifies is counted from its own moment."""
    await _set(hass, LAMP, "off")
    handed, unsub = await _attach(hass, {"entity_id": LAMP}, **{"for": "00:05:00"})

    await _set(hass, LAMP, "on")
    await _later(hass, freezer, 240)
    await _set(hass, LAMP, "off")
    await _later(hass, freezer, 240)
    assert handed == []

    await _later(hass, freezer, 61)
    unsub()

    assert [payload["to_state"].state for payload, _ in handed] == ["off"]


async def test_for_counts_each_entity_on_its_own(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """One door closing does not call off the other."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass, {"entity_id": [FRONT, BACK]}, to="on", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 300)
    unsub()

    assert _fired_for(handed) == [BACK]


async def test_already_there_at_the_start_is_not_counted(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Nothing changed, so there is nothing to have held."""
    await _set(hass, FRONT, "on")
    handed, unsub = await _attach(hass, to="on", **{"for": "00:05:00"})

    await _later(hass, freezer, 600)
    unsub()

    assert handed == []


async def test_first_with_for_needs_one_to_stay(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A second door opening does not start the wait over."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="first",
        **{"for": "00:05:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 120)
    await _set(hass, BACK, "on")
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 181)
    unsub()

    assert _fired_for(handed) == [FRONT]


async def test_first_with_for_is_called_off_when_none_are_left(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The only open door closing ends it."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="first",
        **{"for": "00:05:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 120)
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_all_with_for_is_called_off_when_one_leaves(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """All closed has to hold, together."""
    for door in (FRONT, BACK):
        await _set(hass, door, "on")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="off",
        behavior="all",
        **{"for": "00:05:00"},
    )

    await _set(hass, FRONT, "off")
    await _set(hass, BACK, "off")
    await _later(hass, freezer, 120)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_all_with_for_fires_when_it_held(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Counted from the moment the last one got there."""
    for door in (FRONT, BACK):
        await _set(hass, door, "on")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="off",
        behavior="all",
        **{"for": "00:05:00"},
    )

    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 120)
    await _set(hass, BACK, "off")
    await _later(hass, freezer, 240)
    assert handed == []

    await _later(hass, freezer, 61)
    unsub()

    assert _fired_for(handed) == [BACK]


async def test_a_door_joining_the_target_can_call_off_all(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """All closed is no longer true when an open door gets the label."""
    label = label_registry.async_create("Doors")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    back = entity_registry.async_get_or_create("binary_sensor", "demo", "back")
    entity_registry.async_update_entity(front.entity_id, labels={label.label_id})
    await _set(hass, front.entity_id, "on")
    await _set(hass, back.entity_id, "on")
    handed, unsub = await _attach(
        hass,
        {"label_id": label.label_id},
        to="off",
        behavior="all",
        **{"for": "00:05:00"},
    )

    await _set(hass, front.entity_id, "off")
    await _later(hass, freezer, 60)
    entity_registry.async_update_entity(back.entity_id, labels={label.label_id})
    await hass.async_block_till_done()
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_a_door_leaving_the_target_drops_its_wait(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Whatever it was waiting for is no longer this trigger's business."""
    label = label_registry.async_create("Doors")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    entity_registry.async_update_entity(front.entity_id, labels={label.label_id})
    await _set(hass, front.entity_id, "off")
    handed, unsub = await _attach(
        hass, {"label_id": label.label_id}, to="on", **{"for": "00:05:00"}
    )

    await _set(hass, front.entity_id, "on")
    await _later(hass, freezer, 60)
    entity_registry.async_update_entity(front.entity_id, labels=set())
    await hass.async_block_till_done()
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_removing_the_entity_drops_its_wait(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Gone is not still open."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, to="on", **{"for": "00:05:00"})

    await _set(hass, FRONT, "on")
    hass.states.async_remove(FRONT)
    await hass.async_block_till_done()
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_all_with_for_is_called_off_when_none_are_left_to_ask(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Every door unavailable is not every door closed."""
    for door in (FRONT, BACK):
        await _set(hass, door, "on")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="off",
        behavior="all",
        **{"for": "00:05:00"},
    )

    await _set(hass, FRONT, "off")
    await _set(hass, BACK, "off")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _set(hass, BACK, STATE_UNAVAILABLE)
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_going_unavailable_calls_off_a_wait_for_any_state(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Without a to, unavailable is still not a state that held."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, **{"for": "00:05:00"})

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


# Blip tolerance


@pytest.mark.parametrize("blip", [STATE_UNAVAILABLE, STATE_UNKNOWN])
async def test_a_blip_inside_the_tolerance_is_carried_through(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, blip: str
) -> None:
    """Back as it was, and the wait carries on from where it was."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", blip_tolerance="00:00:30", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, blip)
    await _later(hass, freezer, 20)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 221)
    unsub()

    assert len(handed) == 1


async def test_a_blip_longer_than_the_tolerance_calls_it_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """That was not a blip but an absence."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", blip_tolerance="00:00:30", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 31)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_coming_back_different_calls_it_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Back inside the tolerance, but closed."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", blip_tolerance="00:00:30", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 10)
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_without_a_tolerance_a_blip_calls_it_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The way Home Assistant's own triggers do it."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, to="on", **{"for": "00:05:00"})

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_running_out_during_a_blip_fires_on_the_way_back(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """It held, apart from the blip, so it fires the moment it is back."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", blip_tolerance="00:01:00", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 280)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 30)
    assert handed == []

    await _set(hass, FRONT, "on")
    unsub()

    assert len(handed) == 1


async def test_running_out_during_a_blip_that_lasts_fires_nothing(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Due, but it never came back inside the tolerance."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", blip_tolerance="00:01:00", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 280)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 61)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_the_tolerance_counts_from_the_first_moment_away(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Flickering between unavailable and unknown does not stretch it."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", blip_tolerance="00:00:30", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 20)
    await _set(hass, FRONT, STATE_UNKNOWN)
    await _later(hass, freezer, 11)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


async def test_a_blip_back_does_not_start_the_wait_over(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """With unavailable counting, coming back is still the old wait."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass,
        to="on",
        ignore_unavailable=False,
        blip_tolerance="00:00:30",
        **{"for": "00:05:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 10)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 231)
    unsub()

    assert len(handed) == 1


async def test_a_flicker_inside_a_blip_still_comes_back(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Unavailable, then unknown, then back: one blip, and it is over."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", blip_tolerance="00:00:30", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 10)
    await _set(hass, FRONT, STATE_UNKNOWN)
    await _later(hass, freezer, 10)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 30)
    await _later(hass, freezer, 191)
    unsub()

    assert len(handed) == 1


async def test_a_real_change_is_not_a_blip(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Closing is closing, tolerance or not: the wait starts over after."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", blip_tolerance="00:00:30", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 10)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 240)
    assert handed == []

    await _later(hass, freezer, 61)
    unsub()

    assert len(handed) == 1


async def test_going_away_is_not_a_new_change_when_unavailable_counts(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Without a to, unavailable would pass as a state of its own.

    The blip takes that change for itself, so it neither starts a wait for
    unavailable nor throws away the one for on.
    """
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass,
        ignore_unavailable=False,
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 20)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 5)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 34)
    assert handed == []

    # On time, counted from the first on: the blip did not start it over.
    await _later(hass, freezer, 1)
    assert [p["to_state"].state for p, _ in handed] == ["on"]

    await _later(hass, freezer, 120)
    unsub()

    assert [p["to_state"].state for p, _ in handed] == ["on"]


async def test_going_away_is_a_change_when_to_names_it(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Asked for by name, unavailable is wanted, not a blip to sit out."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass,
        to=["on", STATE_UNAVAILABLE],
        ignore_unavailable=False,
        blip_tolerance="00:00:30",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 20)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 59)
    assert handed == []

    await _later(hass, freezer, 1)
    unsub()

    assert [p["to_state"].state for p, _ in handed] == [STATE_UNAVAILABLE]


async def test_two_blips_each_get_the_full_tolerance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Back in between, so the second one is a blip of its own."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", blip_tolerance="00:00:30", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    for _ in range(2):
        await _later(hass, freezer, 60)
        await _set(hass, FRONT, STATE_UNAVAILABLE)
        await _later(hass, freezer, 25)
        await _set(hass, FRONT, "on")
    await _later(hass, freezer, 131)
    unsub()

    assert len(handed) == 1


async def test_a_blip_of_the_only_one_there_is_carried_for_first(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The tolerance works for the target as a whole too."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="first",
        blip_tolerance="00:00:30",
        **{"for": "00:05:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 10)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 241)
    unsub()

    assert _fired_for(handed) == [FRONT]


async def test_a_blip_of_the_only_one_there_calls_off_first_without_tolerance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Without it, the only open door going away ends the wait."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="first",
        **{"for": "00:05:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 60)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 400)
    unsub()

    assert handed == []


# Delay


async def test_delay_waits_whatever_happens(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Closed again in between, and it still fires, as it was then."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, to="on", delay="00:01:00")

    await _set(hass, FRONT, "on")
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 59)
    assert handed == []

    await _later(hass, freezer, 2)
    unsub()

    assert len(handed) == 1
    payload, _context = handed[0]
    assert payload["to_state"].state == "on"
    assert payload["delay"] == timedelta(minutes=1)


async def test_every_change_waits_on_its_own(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Like a delay in the actions: each run waits for itself."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, delay="00:01:00")

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 30)
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 31)
    assert [payload["to_state"].state for payload, _ in handed] == ["on"]

    await _later(hass, freezer, 30)
    unsub()

    assert [payload["to_state"].state for payload, _ in handed] == ["on", "off"]


async def test_delay_starts_once_for_is_done(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """First it has to hold, then it waits."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", delay="00:01:00", **{"for": "00:05:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 301)
    assert handed == []

    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 60)
    unsub()

    assert len(handed) == 1


async def test_delay_carries_the_context(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Who did it does not change while waiting."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, delay="00:00:10")

    theirs = Context(user_id="abc123")
    await _set(hass, FRONT, "on", context=theirs)
    await _later(hass, freezer, 11)
    unsub()

    assert handed[0][1] is theirs


@pytest.mark.parametrize(
    "options",
    [
        {"delay": "00:01:00"},
        {"for": "00:01:00"},
        {"for": "00:01:00", "delay": "00:01:00"},
    ],
)
async def test_nothing_runs_after_the_trigger_is_gone(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, options: dict[str, Any]
) -> None:
    """An automation turned off or reloaded drops what was waiting."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, **options)

    await _set(hass, FRONT, "on")
    unsub()
    await _later(hass, freezer, 300)

    assert handed == []


# Holding the exact value


@pytest.mark.parametrize(
    "options",
    [
        {"from": "off"},
        {"not_from": "on"},
        {},
    ],
    ids=["from", "not_from", "no filter"],
)
async def test_for_holds_the_value_it_changed_to(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, options: dict[str, Any]
) -> None:
    """Another value is another change, even when it would pass the filters.

    With `from: off`, on and then idle: on did not hold, and on to idle does
    not come from off, so nothing new starts either.
    """
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, **options, **{"for": "00:01:00"})

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 20)
    await _set(hass, FRONT, "idle")
    await _later(hass, freezer, 45)

    on_fired = [p for p, _ in handed if p["to_state"].state == "on"]
    assert on_fired == []
    unsub()


async def test_a_new_value_without_filters_starts_its_own_wait(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Without filters the second change qualifies, and is counted from then."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, **{"for": "00:01:00"})

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 20)
    await _set(hass, FRONT, "idle")
    await _later(hass, freezer, 59)
    assert handed == []

    await _later(hass, freezer, 2)
    unsub()

    assert [p["to_state"].state for p, _ in handed] == ["idle"]


@pytest.mark.parametrize(
    ("options", "back"),
    [
        ({"to": ["on", "open"]}, "open"),
        ({}, "open"),
        ({"not_to": "off"}, "open"),
    ],
)
async def test_back_from_a_blip_as_something_else_calls_it_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    options: dict[str, Any],
    back: str,
) -> None:
    """Back as another value that passes the filters is still not as it was."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, **options, blip_tolerance="00:00:10", **{"for": "00:01:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 20)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 5)
    await _set(hass, FRONT, back)
    await _later(hass, freezer, 120)
    unsub()

    assert [p for p, _ in handed if p["to_state"].state == "on"] == []


async def test_an_attribute_back_from_a_blip_as_another_value_calls_it_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Following brightness: back at 200 is not the 100 that had to hold."""
    await _set(hass, LAMP, "on", {"brightness": 0})
    handed, unsub = await _attach(
        hass,
        {"entity_id": LAMP},
        attribute="brightness",
        to=["100", "200"],
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, LAMP, "on", {"brightness": 100})
    await _later(hass, freezer, 20)
    await _set(hass, LAMP, STATE_UNAVAILABLE)
    await _later(hass, freezer, 5)
    await _set(hass, LAMP, "on", {"brightness": 200})
    await _later(hass, freezer, 50)
    unsub()

    assert handed == []


# Blips and the target as a whole


@pytest.mark.parametrize(
    ("other_state", "other_attributes"),
    [("off", {"battery": 80}), ("idle", None)],
    ids=["attribute update", "different state"],
)
async def test_another_entity_changing_does_not_end_a_group_blip(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    other_state: str,
    other_attributes: dict[str, Any] | None,
) -> None:
    """The back door doing its own thing does not decide the front door's blip."""
    await _set(hass, FRONT, "off")
    await _set(hass, BACK, "off", {"battery": 90})
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="first",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 20)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 2)
    await _set(hass, BACK, other_state, other_attributes)
    await _later(hass, freezer, 3)
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 34)
    assert handed == []

    await _later(hass, freezer, 2)
    unsub()

    assert _fired_for(handed) == [FRONT]


async def test_the_target_growing_does_not_end_a_group_blip(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """A closed door joining does not undo the open one that is away."""
    label = label_registry.async_create("Doors")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    back = entity_registry.async_get_or_create("binary_sensor", "demo", "back")
    entity_registry.async_update_entity(front.entity_id, labels={label.label_id})
    await _set(hass, front.entity_id, "off")
    await _set(hass, back.entity_id, "off")
    handed, unsub = await _attach(
        hass,
        {"label_id": label.label_id},
        to="on",
        behavior="first",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, front.entity_id, "on")
    await _later(hass, freezer, 20)
    await _set(hass, front.entity_id, STATE_UNAVAILABLE)
    await _later(hass, freezer, 2)
    entity_registry.async_update_entity(back.entity_id, labels={label.label_id})
    await hass.async_block_till_done()
    await _later(hass, freezer, 3)
    await _set(hass, front.entity_id, "on")
    await _later(hass, freezer, 36)
    unsub()

    assert _fired_for(handed) == [front.entity_id]


async def test_the_away_one_leaving_the_target_ends_its_blip(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Gone from the target while away: judged without it from then on."""
    label = label_registry.async_create("Doors")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    back = entity_registry.async_get_or_create("binary_sensor", "demo", "back")
    for entry in (front, back):
        entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})
        await _set(hass, entry.entity_id, "off")
    handed, unsub = await _attach(
        hass,
        {"label_id": label.label_id},
        to="on",
        behavior="first",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, front.entity_id, "on")
    await _later(hass, freezer, 20)
    await _set(hass, front.entity_id, STATE_UNAVAILABLE)
    entity_registry.async_update_entity(front.entity_id, labels=set())
    await hass.async_block_till_done()
    await _later(hass, freezer, 60)
    unsub()

    assert handed == []


@pytest.mark.parametrize(
    ("back_after", "fires_at"),
    [(7, 62), (11, None)],
    ids=["inside the tolerance", "outside the tolerance"],
)
async def test_all_with_a_blip_when_unavailable_counts(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    back_after: int,
    fires_at: int | None,
) -> None:
    """With unavailable counting, all waits for the one that went quiet."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="all",
        ignore_unavailable=False,
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 55)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 5)
    assert handed == []

    await _later(hass, freezer, back_after - 5)
    await _set(hass, FRONT, "on")
    if fires_at is None:
        # Too late to carry the old wait, but coming back from unavailable
        # is a change of its own while unavailable counts: a new wait.
        await _later(hass, freezer, 59)
        assert handed == []
        await _later(hass, freezer, 1)
        assert _fired_for(handed) == [FRONT]
    else:
        assert _fired_for(handed) == [BACK]
    unsub()


async def test_all_does_not_wait_for_one_that_no_longer_takes_part(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Ignoring unavailable, the rest are all there on time regardless."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="all",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 55)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 4)
    assert handed == []

    await _later(hass, freezer, 2)
    unsub()

    assert _fired_for(handed) == [BACK]


async def test_all_with_every_one_away_waits_for_their_return(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Nobody left to ask is not all there, so it waits for somebody back."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="all",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 55)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _set(hass, BACK, STATE_UNAVAILABLE)
    await _later(hass, freezer, 7)
    assert handed == []

    await _set(hass, FRONT, "on")
    assert handed == []

    await _set(hass, BACK, "on")
    unsub()

    assert _fired_for(handed) == [BACK]


async def test_all_with_every_one_away_too_long_fires_nothing(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Past the tolerance, nobody taking part is not all there."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="all",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 55)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _set(hass, BACK, STATE_UNAVAILABLE)
    await _later(hass, freezer, 11)
    await _set(hass, FRONT, "on")
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 30)
    unsub()

    assert handed == []


async def test_a_closed_door_going_quiet_is_no_blip_for_first(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Only one that was there takes a blip with it."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="first",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 20)
    await _set(hass, BACK, STATE_UNAVAILABLE)
    await _later(hass, freezer, 30)
    await _set(hass, BACK, "off")
    await _later(hass, freezer, 11)
    unsub()

    assert _fired_for(handed) == [FRONT]


async def test_a_door_that_was_not_open_cannot_hold_first_up(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A closed door going quiet is not a blip that keeps first alive."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="first",
        blip_tolerance="00:00:30",
        **{"for": "00:00:20"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 5)
    await _set(hass, BACK, STATE_UNAVAILABLE)
    await _later(hass, freezer, 5)
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 2)
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 60)
    unsub()

    assert handed == []


async def test_an_attribute_wait_ends_when_the_entity_goes_quiet(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Waiting on brightness being gone is not satisfied by the lamp vanishing."""
    await _set(hass, LAMP, "on", {"brightness": 50})
    handed, unsub = await _attach(
        hass, {"entity_id": LAMP}, attribute="brightness", **{"for": "00:01:00"}
    )

    await _set(hass, LAMP, "off")
    await _later(hass, freezer, 20)
    await _set(hass, LAMP, STATE_UNAVAILABLE)
    await _later(hass, freezer, 60)
    unsub()

    assert handed == []


async def test_first_carries_on_after_a_blip_runs_out_if_it_still_holds(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The front door stays away, but the back door is open: still first."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="first",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 1)
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 19)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 39)
    assert handed == []

    await _later(hass, freezer, 1)
    unsub()

    assert _fired_for(handed) == [FRONT]


async def test_after_a_blip_runs_out_the_away_one_no_longer_counts(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Past the tolerance, the front door is away, not open."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="first",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 1)
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 19)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 20)
    await _set(hass, BACK, "off")
    await _later(hass, freezer, 30)
    assert handed == []

    # The old wait is over, so the back door opening again is first again.
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 60)
    unsub()

    assert _fired_for(handed) == [BACK]


async def test_one_leaving_the_target_while_away_ends_its_blip(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Due, and the rest holds: the one that left is no reason to wait."""
    label = label_registry.async_create("Doors")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    back = entity_registry.async_get_or_create("binary_sensor", "demo", "back")
    for entry in (front, back):
        entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})
        await _set(hass, entry.entity_id, "off")
    handed, unsub = await _attach(
        hass,
        {"label_id": label.label_id},
        to="on",
        behavior="first",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, front.entity_id, "on")
    await _later(hass, freezer, 55)
    await _set(hass, front.entity_id, STATE_UNAVAILABLE)
    await _later(hass, freezer, 7)
    await _set(hass, back.entity_id, "on")
    assert handed == []

    entity_registry.async_update_entity(front.entity_id, labels=set())
    await hass.async_block_till_done()
    unsub()

    assert _fired_for(handed) == [front.entity_id]


async def test_another_door_opening_during_a_blip_is_not_first(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The front door away still counts as open, so the wait is the old one.

    It ran out during the blip, and fires once the blip is over and the back
    door is still open, with the front door's change in it.
    """
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior="first",
        blip_tolerance="00:00:10",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 55)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 7)
    await _set(hass, BACK, "on")
    await _later(hass, freezer, 2)
    assert handed == []

    await _later(hass, freezer, 1)
    assert _fired_for(handed) == [FRONT]

    await _later(hass, freezer, 120)
    unsub()

    assert _fired_for(handed) == [FRONT]


# Timing, exactly


async def test_for_fires_on_time_and_once(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Not before, at the moment, and not again after."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, to="on", **{"for": "00:01:00"})

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 59.5)
    assert handed == []

    await _later(hass, freezer, 0.5)
    assert len(handed) == 1

    await _later(hass, freezer, 120)
    unsub()

    assert len(handed) == 1


async def test_running_out_during_a_blip_fires_exactly_on_return(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Nothing while away, once the moment it is back."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", blip_tolerance="00:00:10", **{"for": "00:01:00"}
    )

    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 55)
    await _set(hass, FRONT, STATE_UNAVAILABLE)
    await _later(hass, freezer, 9)
    assert handed == []

    await _set(hass, FRONT, "on")
    assert len(handed) == 1

    await _later(hass, freezer, 60)
    unsub()

    assert len(handed) == 1


async def test_for_blip_and_delay_together(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Held through a blip, then waits, then fires as it was at the start."""
    await _set(hass, FRONT, "off")
    first = Context(user_id="first")
    handed, unsub = await _attach(
        hass,
        to="on",
        blip_tolerance="00:00:10",
        delay="00:00:20",
        **{"for": "00:01:00"},
    )

    await _set(hass, FRONT, "on", {"by": "first"}, context=first)
    await _later(hass, freezer, 55)
    await _set(hass, FRONT, STATE_UNAVAILABLE, context=Context(user_id="blip"))
    await _later(hass, freezer, 7)
    await _set(hass, FRONT, "on", context=Context(user_id="back"))
    await _later(hass, freezer, 3)
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 16.5)
    assert handed == []

    await _later(hass, freezer, 1)
    unsub()

    assert len(handed) == 1
    payload, context = handed[0]
    assert context is first
    assert payload["from_state"].state == "off"
    assert payload["to_state"].attributes == {"by": "first"}
    assert payload["for"] == timedelta(minutes=1)
    assert payload["delay"] == timedelta(seconds=20)


async def test_a_delay_survives_a_new_wait_starting(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Two changes that each held, two delayed runs, each as it was."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(
        hass, to="on", delay="00:00:30", **{"for": "00:00:10"}
    )

    await _set(hass, FRONT, "on", {"run": 1})
    await _later(hass, freezer, 10)
    await _later(hass, freezer, 2)
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 3)
    await _set(hass, FRONT, "on", {"run": 2})
    await _later(hass, freezer, 5)
    await _set(hass, FRONT, "off")
    await _later(hass, freezer, 19)
    assert handed == []

    await _later(hass, freezer, 1)
    assert [p["to_state"].attributes["run"] for p, _ in handed] == [1]

    await _set(hass, FRONT, "on", {"run": 3})
    await _later(hass, freezer, 10)
    await _later(hass, freezer, 30)
    unsub()

    assert [p["to_state"].attributes["run"] for p, _ in handed] == [1, 3]


@pytest.mark.parametrize(
    ("options", "steps"),
    [
        ({"for": "00:00:10", "delay": "00:00:20"}, [("wait", 15)]),
        (
            {"for": "00:01:00", "blip_tolerance": "00:00:10"},
            [("wait", 55), ("away", 0), ("wait", 2)],
        ),
        (
            {"for": "00:01:00", "blip_tolerance": "00:00:10"},
            [("wait", 55), ("away", 0), ("wait", 7)],
        ),
    ],
    ids=["delay pending", "during a blip", "due during a blip"],
)
async def test_detaching_in_any_phase_drops_everything(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    options: dict[str, Any],
    steps: list[tuple[str, float]],
) -> None:
    """Nothing runs after the automation is turned off, whatever was waiting."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, to="on", **options)

    await _set(hass, FRONT, "on")
    for step, seconds in steps:
        if step == "away":
            await _set(hass, FRONT, STATE_UNAVAILABLE)
        else:
            await _later(hass, freezer, seconds)
    unsub()
    await _set(hass, FRONT, "on")
    await _later(hass, freezer, 300)

    assert handed == []


async def test_detaching_with_several_delays_pending(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Every one of them is dropped, and a fresh trigger starts clean."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(hass, {"entity_id": [FRONT, BACK]}, delay="00:01:00")

    await _set(hass, FRONT, "on")
    await _set(hass, BACK, "on")
    await _set(hass, FRONT, "off")
    unsub()
    await _later(hass, freezer, 120)
    assert handed == []

    handed, unsub = await _attach(hass, {"entity_id": [FRONT, BACK]}, delay="00:01:00")
    await _set(hass, BACK, "off")
    await _later(hass, freezer, 61)
    unsub()

    assert _fired_for(handed) == [BACK]


async def test_a_pending_delay_ignores_the_entity_leaving(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """A delay is a delay: losing the label or the entity does not cancel it."""
    label = label_registry.async_create("Doors")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    entity_registry.async_update_entity(front.entity_id, labels={label.label_id})
    await _set(hass, front.entity_id, "off")
    handed, unsub = await _attach(
        hass, {"label_id": label.label_id}, to="on", delay="00:00:30"
    )

    await _set(hass, front.entity_id, "on")
    await _later(hass, freezer, 10)
    entity_registry.async_update_entity(front.entity_id, labels=set())
    await hass.async_block_till_done()
    hass.states.async_remove(front.entity_id)
    await _later(hass, freezer, 21)
    unsub()

    assert _fired_for(handed) == [front.entity_id]
    assert handed[0][0]["to_state"].state == "on"


# Events that pile up


@pytest.mark.parametrize(
    ("behavior", "expected"),
    [("each", [FRONT, BACK]), ("first", [FRONT]), ("all", [BACK])],
)
async def test_changes_queued_together_are_judged_in_order(
    hass: HomeAssistant, behavior: str, expected: list[str]
) -> None:
    """Judged as they happened, not as the states are once they arrive."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass, {"entity_id": [FRONT, BACK]}, to="on", behavior=behavior
    )

    hass.states.async_set(FRONT, "on")
    hass.states.async_set(BACK, "on")
    hass.states.async_set(FRONT, "off")
    await hass.async_block_till_done()
    unsub()

    assert _fired_for(handed) == expected


@pytest.mark.parametrize(
    ("behavior", "expected"),
    [("each", [BACK]), ("first", [FRONT]), ("all", [])],
)
async def test_changes_queued_together_with_for(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    behavior: str,
    expected: list[str],
) -> None:
    """The same pile-up, held for a minute."""
    for door in (FRONT, BACK):
        await _set(hass, door, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior=behavior,
        **{"for": "00:01:00"},
    )

    hass.states.async_set(FRONT, "on")
    hass.states.async_set(BACK, "on")
    hass.states.async_set(FRONT, "off")
    await hass.async_block_till_done()
    await _later(hass, freezer, 61)
    unsub()

    assert _fired_for(handed) == expected


# Every kind of target


@pytest.fixture(name="house")
def fixture_house(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> dict[str, str]:
    """Return a device on a floor, with a primary, a config and a diagnostic entity."""
    entry = MockConfigEntry(domain="demo")
    entry.add_to_hass(hass)
    floor = fr.async_get(hass).async_create("Ground floor")
    area = area_registry.async_get_or_create("Hallway")
    area_registry.async_update(area.id, floor_id=floor.floor_id)
    label = label_registry.async_create("Front door")
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("demo", "door")}
    )
    device_registry.async_update_device(
        device.id, area_id=area.id, labels={label.label_id}
    )

    def make(domain: str, key: str, category: EntityCategory | None) -> str:
        made = entity_registry.async_get_or_create(
            domain,
            "demo",
            key,
            device_id=device.id,
            config_entry=entry,
            entity_category=category,
        )
        hass.states.async_set(made.entity_id, "off")
        return made.entity_id

    return {
        "primary": make("binary_sensor", "contact", None),
        "config": make("switch", "chime", EntityCategory.CONFIG),
        "diagnostic": make("sensor", "signal", EntityCategory.DIAGNOSTIC),
        "device_id": device.id,
        "area_id": area.id,
        "floor_id": floor.floor_id,
        "label_id": label.label_id,
    }


@pytest.mark.parametrize("kind", ["device_id", "area_id", "floor_id", "label_id"])
async def test_every_indirect_target_keeps_to_primary_entities(
    hass: HomeAssistant, house: dict[str, str], kind: str
) -> None:
    """Device, area, floor or label: the chime and signal settings stay out."""
    handed, unsub = await _attach(hass, {kind: house[kind]})

    for name in ("config", "diagnostic", "primary"):
        await _set(hass, house[name], "on")
    unsub()

    assert _fired_for(handed) == [house["primary"]]


async def test_entities_named_directly_all_count(
    hass: HomeAssistant, house: dict[str, str]
) -> None:
    """Named on purpose, whatever their category."""
    named = [house["primary"], house["config"], house["diagnostic"]]
    handed, unsub = await _attach(hass, {"entity_id": named})

    for entity_id in named:
        await _set(hass, entity_id, "on")
    unsub()

    assert _fired_for(handed) == named


async def test_an_entity_reached_several_ways_fires_once(
    hass: HomeAssistant, house: dict[str, str]
) -> None:
    """Named, and through its device, area, floor and label: still one door."""
    handed, unsub = await _attach(
        hass,
        {
            "entity_id": house["primary"],
            "device_id": house["device_id"],
            "area_id": house["area_id"],
            "floor_id": house["floor_id"],
            "label_id": house["label_id"],
        },
    )

    await _set(hass, house["primary"], "on")
    unsub()

    assert _fired_for(handed) == [house["primary"]]


async def test_a_label_on_a_diagnostic_entity_itself_counts(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """A label put on the entity is naming it, the way Home Assistant sees it."""
    label = label_registry.async_create("Batteries")
    battery = entity_registry.async_get_or_create(
        "sensor", "demo", "battery", entity_category=EntityCategory.DIAGNOSTIC
    )
    entity_registry.async_update_entity(battery.entity_id, labels={label.label_id})
    await _set(hass, battery.entity_id, "80")
    handed, unsub = await _attach(hass, {"label_id": label.label_id})

    await _set(hass, battery.entity_id, "79")
    unsub()

    assert _fired_for(handed) == [battery.entity_id]


@pytest.mark.parametrize("kind", ["device_id", "floor_id", "label_id"])
async def test_every_kind_of_exclude_target_takes_everything(
    hass: HomeAssistant, house: dict[str, str], kind: str
) -> None:
    """Leaving out the device, floor or label leaves out all of its entities."""
    named = [house["primary"], house["config"], house["diagnostic"]]
    handed, unsub = await _attach(
        hass, {"entity_id": named}, exclude_target={kind: house[kind]}
    )

    for entity_id in named:
        await _set(hass, entity_id, "on")
    unsub()

    assert handed == []


@pytest.mark.parametrize(
    "exclude_target",
    [{}, {"entity_id": []}, None],
    ids=["empty", "naming nothing", "left out"],
)
async def test_an_empty_leave_out_is_no_leave_out(
    hass: HomeAssistant, exclude_target: dict[str, Any] | None
) -> None:
    """The exclude lists then apply to everything, however it was written."""
    options: dict[str, Any] = {"exclude_domain": ["binary_sensor"]}
    if exclude_target is not None:
        options["exclude_target"] = exclude_target
    await _set(hass, FRONT, "off")
    validated = await _validate(hass, options)
    handed, unsub = await _attach(hass, **options)

    await _set(hass, FRONT, "on")
    unsub()

    assert "exclude_target" not in validated["options"]
    assert handed == []


# Filters, independently


@pytest.fixture(name="sensors")
def fixture_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, str]:
    """Return sensors that each differ from the full match in one way only."""
    entries = {}
    for entry_id in ("zha_one", "zha_two", "hue_one"):
        entries[entry_id] = MockConfigEntry(domain=entry_id[:3], entry_id=entry_id)
        entries[entry_id].add_to_hass(hass)

    def make(key: str, domain: str, platform: str, entry_id: str, cls: str) -> str:
        made = entity_registry.async_get_or_create(
            domain,
            platform,
            key,
            config_entry=entries[entry_id],
            original_device_class=cls,
        )
        hass.states.async_set(made.entity_id, "off")
        return made.entity_id

    return {
        "match": make("match", "binary_sensor", "zha", "zha_one", "door"),
        "other_entry": make("other_entry", "binary_sensor", "zha", "zha_two", "door"),
        "other_domain": make("other_domain", "switch", "zha", "zha_one", "door"),
        # Registered by another integration than the entry it belongs to,
        # so that integration and entry can be told apart in a test.
        "other_integration": make(
            "other_integration", "binary_sensor", "hue", "zha_one", "door"
        ),
        "other_class": make("other_class", "binary_sensor", "zha", "zha_one", "window"),
    }


_SENSOR_ORDER = (
    "match",
    "other_entry",
    "other_domain",
    "other_integration",
    "other_class",
)


async def _flip_sensors(hass: HomeAssistant, sensors: dict[str, str]) -> None:
    """Turn every sensor on, in a fixed order."""
    for name in _SENSOR_ORDER:
        await _set(hass, sensors[name], "on")


_ALL_FOUR = {
    "domain": ["binary_sensor"],
    "integration": ["zha"],
    "config_entry": ["zha_one"],
    "device_class": ["door"],
}


@pytest.mark.parametrize(
    ("dropped", "also"),
    [
        (None, []),
        ("domain", ["other_domain"]),
        ("integration", ["other_integration"]),
        ("config_entry", ["other_entry"]),
        ("device_class", ["other_class"]),
    ],
)
async def test_each_filter_does_its_own_part(
    hass: HomeAssistant,
    sensors: dict[str, str],
    dropped: str | None,
    also: list[str],
) -> None:
    """All four keep only the full match; dropping one lets its near miss in."""
    options = {key: value for key, value in _ALL_FOUR.items() if key != dropped}
    handed, unsub = await _attach(
        hass, {"entity_id": list(sensors.values())}, **options
    )

    await _flip_sensors(hass, sensors)
    unsub()

    expected = [sensors[n] for n in _SENSOR_ORDER if n in ["match", *also]]
    assert _fired_for(handed) == expected


@pytest.mark.parametrize(
    ("dropped", "also_kept"),
    [
        (None, []),
        ("exclude_domain", ["other_domain"]),
        ("exclude_integration", ["other_integration"]),
        ("exclude_config_entry", ["other_entry"]),
        ("exclude_device_class", ["other_class"]),
    ],
)
async def test_each_exclude_filter_does_its_own_part(
    hass: HomeAssistant,
    sensors: dict[str, str],
    dropped: str | None,
    also_kept: list[str],
) -> None:
    """The same, the other way around: only the full match is left out."""
    options = {
        f"exclude_{key}": value
        for key, value in _ALL_FOUR.items()
        if f"exclude_{key}" != dropped
    }
    handed, unsub = await _attach(
        hass, {"entity_id": list(sensors.values())}, **options
    )

    await _flip_sensors(hass, sensors)
    unsub()

    kept = [n for n in _SENSOR_ORDER if n != "match"]
    if dropped is not None:
        kept = [n for n in kept if n not in also_kept]
    assert _fired_for(handed) == [sensors[n] for n in kept]


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({"config_entry": ["zha_two"]}, ["other_entry"]),
        ({"config_entry": ["zha_two", "zha_one"]}, list(_SENSOR_ORDER)),
        ({"integration": ["hue"]}, ["other_integration"]),
        ({"integration": ["hue", "zha"]}, list(_SENSOR_ORDER)),
        ({"device_class": ["window", "door"]}, list(_SENSOR_ORDER)),
    ],
)
async def test_two_entries_or_integrations_are_either(
    hass: HomeAssistant,
    sensors: dict[str, str],
    options: dict[str, Any],
    expected: list[str],
) -> None:
    """Within one list, any of them will do."""
    handed, unsub = await _attach(
        hass, {"entity_id": list(sensors.values())}, **options
    )

    await _flip_sensors(hass, sensors)
    unsub()

    assert _fired_for(handed) == [sensors[name] for name in expected]


async def test_leave_out_filters_narrow_what_leave_out_names(
    hass: HomeAssistant, sensors: dict[str, str]
) -> None:
    """Out are the ones named AND matching the lists, not either."""
    handed, unsub = await _attach(
        hass,
        {
            "entity_id": [
                sensors["match"],
                sensors["other_entry"],
                sensors["other_class"],
            ]
        },
        exclude_target={"entity_id": [sensors["match"], sensors["other_entry"]]},
        exclude_config_entry=["zha_one"],
    )

    await _flip_sensors(hass, sensors)
    unsub()

    assert _fired_for(handed) == [sensors["other_entry"], sensors["other_class"]]


@pytest.mark.parametrize(
    ("option", "fires"),
    [
        ({"device_class": ["door"]}, True),
        ({"device_class": ["window"]}, False),
        ({"exclude_device_class": ["door"]}, False),
        ({"exclude_device_class": ["window"]}, True),
    ],
)
async def test_the_device_class_set_by_the_user_is_the_one(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    option: dict[str, Any],
    *,
    fires: bool,
) -> None:
    """Shown as a door, it is a door, both to keep and to leave out."""
    sensor = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "contact", original_device_class="window"
    )
    entity_registry.async_update_entity(sensor.entity_id, device_class="door")
    await _set(hass, sensor.entity_id, "off", {"device_class": "motion"})
    handed, unsub = await _attach(hass, {"entity_id": sensor.entity_id}, **option)

    await _set(hass, sensor.entity_id, "on", {"device_class": "motion"})
    unsub()

    assert bool(handed) is fires


async def test_a_filter_follows_the_registry_as_it_changes(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Becoming a door makes it count, and stopping being one makes it stop."""
    sensor = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "contact", original_device_class="window"
    )
    await _set(hass, sensor.entity_id, "off")
    handed, unsub = await _attach(
        hass, {"entity_id": sensor.entity_id}, device_class=["door"]
    )

    await _set(hass, sensor.entity_id, "on")
    entity_registry.async_update_entity(sensor.entity_id, device_class="door")
    await hass.async_block_till_done()
    await _set(hass, sensor.entity_id, "off")
    entity_registry.async_update_entity(sensor.entity_id, device_class="window")
    await hass.async_block_till_done()
    await _set(hass, sensor.entity_id, "on")
    unsub()

    assert [p["to_state"].state for p, _ in handed] == ["off"]


# The target changing while a group waits


async def test_first_keeps_waiting_when_another_one_is_still_there(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """The one that started it leaving does not matter while another is open."""
    label = label_registry.async_create("Doors")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    back = entity_registry.async_get_or_create("binary_sensor", "demo", "back")
    for entry in (front, back):
        entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})
        await _set(hass, entry.entity_id, "off")
    handed, unsub = await _attach(
        hass,
        {"label_id": label.label_id},
        to="on",
        behavior="first",
        **{"for": "00:01:00"},
    )

    await _set(hass, front.entity_id, "on")
    await _later(hass, freezer, 10)
    await _set(hass, back.entity_id, "on")
    await _later(hass, freezer, 10)
    entity_registry.async_update_entity(front.entity_id, labels=set())
    await hass.async_block_till_done()
    await _later(hass, freezer, 39)
    assert handed == []

    await _later(hass, freezer, 2)
    unsub()

    assert _fired_for(handed) == [front.entity_id]
    assert handed[0][0]["to_state"].state == "on"


@pytest.mark.parametrize("change", ["join while there", "member leaves"])
async def test_all_keeps_waiting_when_it_still_holds(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
    change: str,
) -> None:
    """An open door joining, or one of them leaving, keeps all of them open."""
    label = label_registry.async_create("Doors")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    back = entity_registry.async_get_or_create("binary_sensor", "demo", "back")
    side = entity_registry.async_get_or_create("binary_sensor", "demo", "side")
    for entry in (front, back):
        entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})
    for entry in (front, back, side):
        await _set(hass, entry.entity_id, "off")
    handed, unsub = await _attach(
        hass,
        {"label_id": label.label_id},
        to="on",
        behavior="all",
        **{"for": "00:01:00"},
    )

    await _set(hass, side.entity_id, "on")
    await _set(hass, front.entity_id, "on")
    await _set(hass, back.entity_id, "on")
    await _later(hass, freezer, 20)
    if change == "join while there":
        entity_registry.async_update_entity(side.entity_id, labels={label.label_id})
    else:
        entity_registry.async_update_entity(front.entity_id, labels=set())
    await hass.async_block_till_done()
    await _later(hass, freezer, 41)
    unsub()

    assert _fired_for(handed) == [back.entity_id]


async def test_all_ends_when_the_last_member_leaves(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """No members left is not all of them there."""
    label = label_registry.async_create("Doors")
    front = entity_registry.async_get_or_create("binary_sensor", "demo", "front")
    entity_registry.async_update_entity(front.entity_id, labels={label.label_id})
    await _set(hass, front.entity_id, "off")
    handed, unsub = await _attach(
        hass,
        {"label_id": label.label_id},
        to="on",
        behavior="all",
        **{"for": "00:01:00"},
    )

    await _set(hass, front.entity_id, "on")
    await _later(hass, freezer, 20)
    entity_registry.async_update_entity(front.entity_id, labels=set())
    await hass.async_block_till_done()
    await _later(hass, freezer, 60)
    unsub()

    assert handed == []


@pytest.mark.parametrize("behavior", ["first", "all"])
async def test_a_group_already_there_at_the_start_is_not_counted(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, behavior: str
) -> None:
    """Nothing changed, so first or all did not just happen."""
    for door in (FRONT, BACK):
        await _set(hass, door, "on")
    handed, unsub = await _attach(
        hass,
        {"entity_id": [FRONT, BACK]},
        to="on",
        behavior=behavior,
        **{"for": "00:01:00"},
    )

    await _later(hass, freezer, 120)
    unsub()

    assert handed == []


# Attributes over time


async def test_following_an_attribute_ignores_the_state_while_waiting(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The brightness held; the state flipping around it does not matter."""
    await _set(hass, LAMP, "on", {"brightness": 0})
    handed, unsub = await _attach(
        hass,
        {"entity_id": LAMP},
        attribute="brightness",
        to="100",
        **{"for": "00:01:00"},
    )

    await _set(hass, LAMP, "on", {"brightness": 100})
    await _later(hass, freezer, 10)
    await _set(hass, LAMP, "flashing", {"brightness": 100})
    await _later(hass, freezer, 51)
    unsub()

    assert len(handed) == 1


async def test_an_attribute_disappearing_ends_the_wait(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Gone is not 100."""
    await _set(hass, LAMP, "on", {"brightness": 0})
    handed, unsub = await _attach(
        hass,
        {"entity_id": LAMP},
        attribute="brightness",
        to="100",
        **{"for": "00:01:00"},
    )

    await _set(hass, LAMP, "on", {"brightness": 100})
    await _later(hass, freezer, 20)
    await _set(hass, LAMP, "on")
    await _later(hass, freezer, 60)
    unsub()

    assert handed == []


async def test_all_on_an_attribute(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Both lamps at 100, held from the moment the second got there."""
    other = "light.other"
    for lamp in (LAMP, other):
        await _set(hass, lamp, "on", {"brightness": 0})
    handed, unsub = await _attach(
        hass,
        {"entity_id": [LAMP, other]},
        attribute="brightness",
        to="100",
        behavior="all",
        **{"for": "00:01:00"},
    )

    await _set(hass, LAMP, "on", {"brightness": 100})
    await _later(hass, freezer, 20)
    await _set(hass, other, "on", {"brightness": 100})
    await _later(hass, freezer, 59)
    assert handed == []

    await _later(hass, freezer, 2)
    unsub()

    assert _fired_for(handed) == [other]


@pytest.mark.parametrize(
    ("before", "after", "fires"),
    [
        ({"brightness": 100}, {"brightness": "100"}, False),
        ({"brightness": 100}, {}, True),
        ({}, {"brightness": None}, False),
        ({"brightness": None}, {"brightness": "None"}, True),
    ],
    ids=["number to text", "to gone", "gone to none", "none to the text none"],
)
async def test_what_counts_as_another_attribute_value(
    hass: HomeAssistant,
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    fires: bool,
) -> None:
    """Compared as text, with missing and None both being no value."""
    await _set(hass, LAMP, "on", before)
    handed, unsub = await _attach(hass, {"entity_id": LAMP}, attribute="brightness")

    await _set(hass, LAMP, "on", after)
    unsub()

    assert len(handed) == int(fires)


async def test_to_the_text_none_is_not_a_missing_value(hass: HomeAssistant) -> None:
    """Typing None asks for the text, not for the attribute to be gone."""
    await _set(hass, LAMP, "on", {"effect": "rainbow"})
    handed, unsub = await _attach(
        hass, {"entity_id": LAMP}, attribute="effect", to="None"
    )

    await _set(hass, LAMP, "on")
    await _set(hass, LAMP, "on", {"effect": "None"})
    unsub()

    assert len(handed) == 1


async def test_attribute_noise_restarts_the_wait_when_it_counts(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """With attribute changes counting, each one is a new change to hold."""
    await _set(hass, LAMP, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": LAMP},
        to="on",
        attribute_changes=True,
        **{"for": "00:01:00"},
    )

    await _set(hass, LAMP, "on", {"brightness": 10})
    await _later(hass, freezer, 20)
    await _set(hass, LAMP, "on", {"brightness": 20})
    await _later(hass, freezer, 41)
    assert handed == []

    await _later(hass, freezer, 20)
    unsub()

    assert handed[0][0]["to_state"].attributes == {"brightness": 20}


@pytest.mark.parametrize("counts", [None, False])
async def test_attribute_noise_does_not_restart_the_wait(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, *, counts: bool | None
) -> None:
    """Left out or off, the brightness moving does not touch the wait."""
    await _set(hass, LAMP, "off")
    options: dict[str, Any] = {"to": "on", "for": "00:01:00"}
    if counts is not None:
        options["attribute_changes"] = counts
    handed, unsub = await _attach(hass, {"entity_id": LAMP}, **options)

    await _set(hass, LAMP, "on", {"brightness": 10})
    await _later(hass, freezer, 20)
    await _set(hass, LAMP, "on", {"brightness": 20})
    await _later(hass, freezer, 41)
    unsub()

    assert handed[0][0]["to_state"].attributes == {"brightness": 10}


@pytest.mark.parametrize("behavior", ["first", "all"])
async def test_attribute_noise_keeps_a_group_deadline(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, behavior: str
) -> None:
    """The count did not move, so the group keeps its moment."""
    await _set(hass, LAMP, "off")
    handed, unsub = await _attach(
        hass,
        {"entity_id": LAMP},
        to="on",
        behavior=behavior,
        attribute_changes=True,
        **{"for": "00:01:00"},
    )

    await _set(hass, LAMP, "on", {"brightness": 10})
    await _later(hass, freezer, 20)
    await _set(hass, LAMP, "on", {"brightness": 20})
    await _later(hass, freezer, 41)
    unsub()

    assert len(handed) == 1


# The full matrix of nothing to say


_STATES = ["on", STATE_UNKNOWN, STATE_UNAVAILABLE]


@pytest.mark.parametrize("old", _STATES)
@pytest.mark.parametrize("new", _STATES)
@pytest.mark.parametrize("ignore", [True, False])
async def test_every_transition_through_unknown_and_unavailable(
    hass: HomeAssistant, old: str, new: str, *, ignore: bool
) -> None:
    """Ignored, anything touching them is left out; counted, they are states."""
    await _set(hass, FRONT, old, {"n": 1})
    handed, unsub = await _attach(
        hass, ignore_unavailable=ignore, attribute_changes=True
    )

    await _set(hass, FRONT, new, {"n": 2})
    unsub()

    touches_quiet = {old, new} & {STATE_UNKNOWN, STATE_UNAVAILABLE}
    assert len(handed) == int(not (ignore and touches_quiet))


async def test_a_restored_state_counts_when_unavailable_counts(
    hass: HomeAssistant,
) -> None:
    """With the ignoring off, a restart is a change like any other."""
    await _set(hass, FRONT, "off")
    handed, unsub = await _attach(hass, ignore_unavailable=False)

    await _set(hass, FRONT, STATE_UNAVAILABLE, {"restored": True})
    await _set(hass, FRONT, "off")
    unsub()

    assert [p["to_state"].state for p, _ in handed] == [STATE_UNAVAILABLE, "off"]


# Filters on both sides, exactly


@pytest.mark.parametrize(
    ("options", "old", "new", "fires"),
    [
        ({"from": "off", "not_to": "idle"}, "off", "on", True),
        ({"from": "off", "not_to": "idle"}, "blocked", "on", False),
        ({"from": "off", "not_to": "idle"}, "off", "idle", False),
        ({"not_from": "blocked", "to": "on"}, "off", "on", True),
        ({"not_from": "blocked", "to": "on"}, "blocked", "on", False),
        ({"not_from": "blocked", "to": "on"}, "off", "idle", False),
        ({"not_from": "blocked", "not_to": "idle"}, "off", "on", True),
        ({"not_from": "blocked", "not_to": "idle"}, "blocked", "on", False),
        ({"not_from": "blocked", "not_to": "idle"}, "off", "idle", False),
        ({"from": ["off", "idle"], "to": ["on", "open"]}, "idle", "open", True),
        ({"from": ["off", "idle"], "to": ["on", "open"]}, "on", "open", False),
    ],
)
async def test_both_sides_count_exactly_once(
    hass: HomeAssistant,
    options: dict[str, Any],
    old: str,
    new: str,
    *,
    fires: bool,
) -> None:
    """One firing when both sides pass, none when either side does not."""
    await _set(hass, FRONT, old)
    handed, unsub = await _attach(hass, **options)

    await _set(hass, FRONT, new)
    unsub()

    assert len(handed) == int(fires)


# The whole path


async def test_it_works_in_an_automation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Configured the way an automation does it, through the whole path."""
    label = label_registry.async_create("Outside door")
    door = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "door", original_device_class="door"
    )
    window = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "window", original_device_class="window"
    )
    for entry in (door, window):
        entity_registry.async_update_entity(entry.entity_id, labels={label.label_id})
        hass.states.async_set(entry.entity_id, "off")

    ran: list[str] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["entity_id"])

    hass.services.async_register("test", "mark", _mark)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "triggers": {
                    "trigger": "spook.state_changed",
                    "target": {"label_id": label.label_id},
                    "options": {"device_class": "door", "to": "on"},
                },
                "actions": {
                    "action": "test.mark",
                    "data": {"entity_id": "{{ trigger.entity_id }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    await _set(hass, window.entity_id, "on")
    await _set(hass, door.entity_id, "on")
    await _set(hass, door.entity_id, STATE_UNAVAILABLE)
    await _set(hass, door.entity_id, "on")

    assert ran == [door.entity_id]


async def test_it_works_in_an_automation_without_a_target(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Every door in the house, the whole way through."""
    door = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "door", original_device_class="door"
    )
    window = entity_registry.async_get_or_create(
        "binary_sensor", "demo", "window", original_device_class="window"
    )
    for entry in (door, window):
        hass.states.async_set(entry.entity_id, "off")

    ran: list[str] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["entity_id"])

    hass.services.async_register("test", "mark", _mark)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "triggers": {
                    "trigger": "spook.state_changed",
                    "options": {"device_class": "door", "to": "on"},
                },
                "actions": {
                    "action": "test.mark",
                    "data": {"entity_id": "{{ trigger.entity_id }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    await _set(hass, window.entity_id, "on")
    await _set(hass, door.entity_id, "on")

    assert ran == [door.entity_id]
