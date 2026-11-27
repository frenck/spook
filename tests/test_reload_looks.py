"""Tests for which reloads send a repair in for another look."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.components.automation import EVENT_AUTOMATION_RELOADED
from homeassistant.const import (
    EVENT_CALL_SERVICE,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import State
from homeassistant.setup import async_setup_component

import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.spook.repairs import AbstractSpookRepair

# Repairs that hear about every change they care about where it happens, so
# a reload of some other domain is no reason for them to look, and neither
# is the call of their own: they hear when that one is done.
_NOT_WOKEN_BY_OTHER_RELOADS = [
    "alert.repairs.unknown_entity_references",
    "alert.repairs.unknown_notifiers",
    "automation.repairs.never_true_templates",
    "automation.repairs.unknown_area_references",
    "automation.repairs.unknown_condition_references",
    "automation.repairs.unknown_config_entry_references",
    "automation.repairs.unknown_device_references",
    "automation.repairs.unknown_floor_references",
    "automation.repairs.unknown_icons",
    "automation.repairs.unknown_label_references",
    "automation.repairs.unknown_service_references",
    "automation.repairs.unknown_trigger_id_references",
    "automation.repairs.unknown_trigger_references",
    "automation.repairs.unknown_user_references",
    "homeassistant.repairs.empty_areas",
    "homeassistant.repairs.empty_floors",
    "homeassistant.repairs.unused_blueprints",
    "homeassistant.repairs.unused_labels",
    "lovelace.repairs.unknown_area_references",
    "lovelace.repairs.unknown_icons",
    "lovelace.repairs.unknown_service_references",
    "lovelace.repairs.unknown_theme_references",
    "lovelace.repairs.unknown_user_references",
    "lovelace.repairs.unknown_view_references",
    "notify.repairs.unknown_group_members",
    "script.repairs.never_true_templates",
    "script.repairs.unknown_area_references",
    "script.repairs.unknown_condition_references",
    "script.repairs.unknown_config_entry_references",
    "script.repairs.unknown_device_references",
    "script.repairs.unknown_floor_references",
    "script.repairs.unknown_icons",
    "script.repairs.unknown_label_references",
    "script.repairs.unknown_service_references",
    "script.repairs.unknown_trigger_references",
    "script.repairs.unknown_user_references",
    "person.repairs.unknown_device_trackers",
    "group.repairs.unknown_members",
]

_AUTOMATION_REPAIRS = [
    name for name in _NOT_WOKEN_BY_OTHER_RELOADS if name.startswith("automation.")
]
_SCRIPT_REPAIRS = [
    name for name in _NOT_WOKEN_BY_OTHER_RELOADS if name.startswith("script.")
]

# Repairs about entity references: an entity of any domain coming or going
# is a reason for them to look, and so is an action, as a name that is an
# action is no unknown entity.
_ENTITY_REFERENCE_REPAIRS = [
    "automation.repairs.unknown_entity_references",
    "lovelace.repairs.unknown_entity_references",
    "scene.repairs.unknown_entity_references",
    "script.repairs.unknown_entity_references",
]

# Every script repair that looks again when a script comes or goes, the
# ones about attributes, states and entities included.
_LOOKING_WHEN_SCRIPTS_COME_OR_GO = [
    *_SCRIPT_REPAIRS,
    "script.repairs.unknown_attribute_references",
    "script.repairs.unknown_entity_references",
    "script.repairs.unknown_state_references",
]


def _repair_class(module: str) -> type[AbstractSpookRepair]:
    """Return the repair a module of the ectoplasms holds."""
    return import_module(f"custom_components.spook.ectoplasms.{module}").SpookRepair


def _counted_looks(repair: AbstractSpookRepair) -> list[None]:
    """Swap an activated repair's debouncer for a list of the looks asked for."""
    repair.inspect_debouncer.async_shutdown()
    looks: list[None] = []

    async def _async_asked() -> None:
        looks.append(None)

    repair.inspect_debouncer = SimpleNamespace(
        async_call=_async_asked,
        async_schedule_call=lambda: looks.append(None),
        async_shutdown=lambda: None,
    )
    return looks


async def _count_looks_asked_for(
    hass: HomeAssistant, repair: AbstractSpookRepair, event_type: str, data: dict
) -> int:
    """Return how many looks one event asks an activated repair for."""
    looks = _counted_looks(repair)

    hass.bus.async_fire(event_type, data)
    await hass.async_block_till_done()
    return len(looks)


@pytest.fixture(name="dashboards", autouse=True)
def dashboards_fixture(hass: HomeAssistant) -> None:
    """Give the dashboard repairs a Lovelace without dashboards to read."""
    hass.data["lovelace"] = SimpleNamespace(dashboards={})


@pytest.mark.parametrize(
    "module", [*_NOT_WOKEN_BY_OTHER_RELOADS, *_ENTITY_REFERENCE_REPAIRS]
)
@pytest.mark.parametrize("domain", ["template", "group", "script", "input_select"])
async def test_a_reload_elsewhere_is_no_reason_to_look(
    hass: HomeAssistant, module: str, domain: str
) -> None:
    """Test a reload of another domain leaves these repairs alone.

    Every one of them used to look again after every reload of any domain,
    45 rounds for a single `template.reload`, for changes they already hear
    about where those happen: entities and actions coming and going,
    registries, dashboards, their own reload event, or their own entities
    coming back once their reload is done.
    """
    repair = _repair_class(module)(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(
        hass,
        repair,
        EVENT_CALL_SERVICE,
        {"domain": domain, "service": "reload", "service_data": {}},
    )
    await repair.async_deactivate()

    assert looks == 0


@pytest.mark.parametrize(
    "module", [*_AUTOMATION_REPAIRS, "automation.repairs.unknown_entity_references"]
)
async def test_automation_repairs_look_once_their_reload_is_done(
    hass: HomeAssistant, module: str
) -> None:
    """Test an automation repair looks again once the automations reloaded.

    That is the look that sees the new configuration. The one the reload
    call used to start came three seconds after the call, finished or not.
    """
    repair = _repair_class(module)(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(hass, repair, EVENT_AUTOMATION_RELOADED, {})
    await repair.async_deactivate()

    assert looks == 1


_ADDED = {"old_state": None, "new_state": State("script.wake_up", "off")}
_REMOVED = {"old_state": State("script.wake_up", "off"), "new_state": None}
_RAN = {
    "old_state": State("script.wake_up", "off"),
    "new_state": State("script.wake_up", "on"),
}


@pytest.mark.parametrize("module", _SCRIPT_REPAIRS)
@pytest.mark.parametrize(
    ("change", "expected_looks"),
    [
        ({"entity_id": "script.wake_up", **_ADDED}, 1),
        ({"entity_id": "script.wake_up", **_REMOVED}, 1),
        ({"entity_id": "script.wake_up", **_RAN}, 0),
        ({"entity_id": "light.kitchen", **_ADDED}, 0),
    ],
    ids=["script added", "script removed", "script ran", "other entity added"],
)
async def test_script_repairs_look_once_their_reload_is_done(
    hass: HomeAssistant, module: str, change: dict, expected_looks: int
) -> None:
    """Test a script repair looks again when one of the scripts comes or goes.

    Scripts send no event when they reloaded. What a reload does: every
    script that changed is removed, and added back once it is done, so that
    is the look that sees the new configuration.
    """
    repair = _repair_class(module)(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(hass, repair, EVENT_STATE_CHANGED, change)
    await repair.async_deactivate()

    assert looks == expected_looks


def _scripts(sequence: list[Any]) -> dict[str, Any]:
    """Return a configuration holding one script."""
    return {"script": {"wake_up": {"sequence": sequence}}}


async def _looks_after_a_reload(
    hass: HomeAssistant,
    module: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> int:
    """Return how many looks a real reload asks a repair for.

    Sets up the one domain ``before`` holds, then reloads it with ``after``
    as the configuration it reads back.
    """
    (domain,) = before
    assert await async_setup_component(hass, domain, before)
    await hass.async_block_till_done()
    repair = _repair_class(module)(hass)
    await repair.async_activate()
    looks = _counted_looks(repair)

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=after,
    ):
        await hass.services.async_call(domain, "reload", blocking=True)
    await hass.async_block_till_done()
    await repair.async_deactivate()

    return len(looks)


async def _looks_after_a_script_reload(
    hass: HomeAssistant, module: str, sequence: list[Any]
) -> int:
    """Return how many looks a real script reload asks a repair for."""
    return await _looks_after_a_reload(hass, module, _scripts([]), _scripts(sequence))


@pytest.mark.parametrize("module", _LOOKING_WHEN_SCRIPTS_COME_OR_GO)
async def test_script_repairs_look_after_an_edited_script_reloads(
    hass: HomeAssistant, module: str
) -> None:
    """Test an edited script, really reloaded, gets a look.

    A script is in the entity registry, so a reload never takes its state
    away: it turns unavailable and restored until the script is back. That
    has to count as the script going and coming back, or no reload would.
    """
    assert await _looks_after_a_script_reload(hass, module, [{"delay": 1}])


@pytest.mark.parametrize("module", _LOOKING_WHEN_SCRIPTS_COME_OR_GO)
async def test_script_repairs_leave_a_reload_that_changed_nothing_alone(
    hass: HomeAssistant, module: str
) -> None:
    """Test a reload that left every script as it was asks for no look."""
    assert await _looks_after_a_script_reload(hass, module, []) == 0


@pytest.mark.parametrize("module", _ENTITY_REFERENCE_REPAIRS)
@pytest.mark.parametrize(
    "event_type", [EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED]
)
async def test_entity_reference_repairs_look_when_an_action_comes_or_goes(
    hass: HomeAssistant, module: str, event_type: str
) -> None:
    """Test a legacy notify action coming or going gets a look.

    A name like `notify.my_phone` is an action, not an unknown entity, for
    as long as that action is there. A reload of the integration behind it
    used to be the only thing that brought a look when it went.
    """
    repair = _repair_class(module)(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(
        hass, repair, event_type, {"domain": "notify", "service": "my_phone"}
    )
    await repair.async_deactivate()

    assert looks == 1


@pytest.mark.parametrize(
    "module", [*_ENTITY_REFERENCE_REPAIRS, "group.repairs.unknown_members"]
)
async def test_entity_reference_repairs_look_when_any_entity_comes(
    hass: HomeAssistant, module: str
) -> None:
    """Test an entity of another domain appearing gets a look.

    Plenty of entities never touch the entity registry. One set by a script
    or a template without a unique ID only ever arrives as a state.
    """
    repair = _repair_class(module)(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(
        hass,
        repair,
        EVENT_STATE_CHANGED,
        {
            "entity_id": "sensor.made_up",
            "old_state": None,
            "new_state": State("sensor.made_up", "1"),
        },
    )
    await repair.async_deactivate()

    assert looks == 1


def _people(device_trackers: list[str]) -> dict[str, Any]:
    """Return a configuration holding one person."""
    return {
        "person": [
            {"id": "frenck", "name": "Frenck", "device_trackers": device_trackers}
        ]
    }


async def test_person_repair_looks_after_a_person_reload(hass: HomeAssistant) -> None:
    """Test a person, really reloaded with other trackers, gets a look.

    A person changes in place: the reload hands the new configuration to
    the entity that is already there. Nothing goes or comes, and there is
    no reload event, so the state listing its device trackers is the sign.
    """
    looks = await _looks_after_a_reload(
        hass,
        "person.repairs.unknown_device_trackers",
        _people(["device_tracker.phone"]),
        _people(["device_tracker.phone", "device_tracker.watch"]),
    )

    assert looks


async def test_person_repair_leaves_a_reload_that_changed_nothing_alone(
    hass: HomeAssistant,
) -> None:
    """Test a person reload that left every person as it was asks for no look."""
    people = _people(["device_tracker.phone"])

    looks = await _looks_after_a_reload(
        hass, "person.repairs.unknown_device_trackers", people, people
    )

    assert looks == 0


async def test_person_repair_leaves_a_person_moving_around_alone(
    hass: HomeAssistant,
) -> None:
    """Test a person changing state, trackers and all the same, asks for no look.

    A person's state changes with every step its device trackers take, so
    only a change to the trackers it lists is worth a look.
    """
    trackers = {"device_trackers": ["device_tracker.phone"]}
    repair = _repair_class("person.repairs.unknown_device_trackers")(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(
        hass,
        repair,
        EVENT_STATE_CHANGED,
        {
            "entity_id": "person.frenck",
            "old_state": State("person.frenck", "home", trackers),
            "new_state": State("person.frenck", "not_home", trackers),
        },
    )
    await repair.async_deactivate()

    assert looks == 0


_GROUP_REPAIR = "group.repairs.unknown_members"


async def _looks_after_a_group_reload(
    hass: HomeAssistant, before: dict[str, Any], after: dict[str, Any]
) -> int:
    """Return how many looks a real group reload asks the group repair for."""
    # Set up once, with what it holds: a second setup is not read again.
    assert await async_setup_component(
        hass, "group", {"group": before.get("group", {})}
    )
    for domain, config in before.items():
        if domain != "group":
            assert await async_setup_component(hass, domain, {domain: config})
    await hass.async_block_till_done()
    repair = _repair_class(_GROUP_REPAIR)(hass)
    await repair.async_activate()
    # The look before the reload, that knows which groups there are.
    await repair.async_inspect()
    looks = _counted_looks(repair)

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=after,
    ):
        await hass.services.async_call("group", "reload", blocking=True)
    await hass.async_block_till_done()
    await repair.async_deactivate()

    return len(looks)


def _light_group(members: list[str]) -> dict[str, Any]:
    """Return a configuration holding one light group, in the registry."""
    return {
        "light": [
            {
                "platform": "group",
                "name": "Kitchen",
                "unique_id": "kitchen",
                "entities": members,
            }
        ]
    }


async def test_group_repair_looks_after_a_light_group_reloads(
    hass: HomeAssistant,
) -> None:
    """Test a light group, really reloaded with other members, gets a look.

    It is in the entity registry, so the reload never takes its state away:
    it turns unavailable and restored, and comes back with its new members.
    No entity goes or comes along the way, and there is no reload event.
    """
    looks = await _looks_after_a_group_reload(
        hass,
        _light_group(["light.ceiling"]),
        _light_group(["light.ceiling", "light.counter"]),
    )

    assert looks


async def test_group_repair_looks_after_an_old_style_group_reloads(
    hass: HomeAssistant,
) -> None:
    """Test a `group.` group, really reloaded with other members, gets a look."""
    looks = await _looks_after_a_group_reload(
        hass,
        {"group": {"kitchen": {"entities": ["light.ceiling"]}}},
        {"group": {"kitchen": {"entities": ["light.ceiling", "light.counter"]}}},
    )

    assert hass.states.get("group.kitchen").attributes["entity_id"] == (
        "light.ceiling",
        "light.counter",
    )
    assert looks


@pytest.mark.parametrize(
    ("entity_id", "old_attributes", "new_attributes"),
    [
        (
            "light.kitchen",
            {"entity_id": ["light.ceiling"]},
            {"entity_id": ["light.ceiling"]},
        ),
        ("light.kitchen", {"entity_id": ["light.ceiling"]}, {}),
        ("sensor.calibrated", {"entity_id": "sensor.raw"}, {}),
        ("light.ceiling", {"brightness": 10}, {"brightness": 200}),
    ],
    ids=[
        "group switched on",
        "group went unavailable",
        "helper naming its source went unavailable",
        "other entity changed",
    ],
)
async def test_group_repair_leaves_a_group_doing_its_job_alone(
    hass: HomeAssistant,
    entity_id: str,
    old_attributes: dict[str, Any],
    new_attributes: dict[str, Any],
) -> None:
    """Test a state change that lists the same members asks for no look."""
    repair = _repair_class(_GROUP_REPAIR)(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(
        hass,
        repair,
        EVENT_STATE_CHANGED,
        {
            "entity_id": entity_id,
            "old_state": State(entity_id, "off", old_attributes),
            "new_state": State(entity_id, "on", new_attributes),
        },
    )
    await repair.async_deactivate()

    assert looks == 0


async def test_group_repair_looks_when_group_set_changes_the_members(
    hass: HomeAssistant,
) -> None:
    """Test `group.set` changing a group's members in place gets a look.

    Nothing goes, comes or reloads: the group that is there takes other
    members and writes them down, and that is all there is to hear.
    """
    assert await async_setup_component(hass, "group", {"group": {}})
    await hass.services.async_call(
        "group",
        "set",
        {"object_id": "kitchen", "entities": ["light.ceiling"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    repair = _repair_class(_GROUP_REPAIR)(hass)
    await repair.async_activate()
    await repair.async_inspect()
    looks = _counted_looks(repair)

    await hass.services.async_call(
        "group",
        "set",
        {"object_id": "kitchen", "entities": ["light.ceiling", "light.counter"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    await repair.async_deactivate()

    assert looks


async def test_group_repair_remembers_a_group_through_its_reload(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a group missed by a look in the middle of its reload still counts.

    A group being reloaded is missing from its platform until it is back.
    When it comes back unavailable it lists no members, so the restored
    state it leaves is all there is to go by.
    """
    assert await async_setup_component(hass, "group", {"group": {}})
    assert await async_setup_component(hass, "light", _light_group(["light.gone"]))
    await hass.async_block_till_done()
    repair = _repair_class(_GROUP_REPAIR)(hass)
    await repair.async_activate()
    await repair.async_inspect()

    # The look in the middle of the reload, with the group not back yet.
    monkeypatch.setattr(
        "custom_components.spook.ectoplasms.group.repairs.unknown_members"
        ".async_group_members",
        lambda _hass: iter(()),
    )
    await repair.async_inspect()

    looks = await _count_looks_asked_for(
        hass,
        repair,
        EVENT_STATE_CHANGED,
        {
            "entity_id": "light.kitchen",
            "old_state": State("light.kitchen", "unavailable", {"restored": True}),
            "new_state": State("light.kitchen", "unavailable"),
        },
    )
    await repair.async_deactivate()

    assert looks == 1


_SCENE_REPAIR = "scene.repairs.unknown_entity_references"


def _scenes(state: str) -> dict[str, Any]:
    """Return a configuration holding one scene, in the registry like an edited one."""
    return {
        "scene": [
            {"id": "evening", "name": "Evening", "entities": {"light.ceiling": state}}
        ]
    }


async def test_scene_repair_looks_after_a_scene_reload(hass: HomeAssistant) -> None:
    """Test a scene, really reloaded with other states, gets a look."""
    looks = await _looks_after_a_reload(
        hass, _SCENE_REPAIR, _scenes("on"), _scenes("off")
    )

    assert looks


async def test_scene_repair_looks_once_scenes_reloaded(hass: HomeAssistant) -> None:
    """Test the scene repair looks again once the scenes reloaded.

    That is the look that sees the new configuration, an edit in the scene
    editor included: saving one reloads the scenes.
    """
    repair = _repair_class(_SCENE_REPAIR)(hass)
    await repair.async_activate()

    looks = await _count_looks_asked_for(hass, repair, "scene_reloaded", {})
    await repair.async_deactivate()

    assert looks == 1
