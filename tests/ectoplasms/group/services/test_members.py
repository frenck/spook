"""Tests for the group member actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.group.config_flow import GroupConfigFlowHandler
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

import pytest

from custom_components.spook.ectoplasms.group.services import (
    add_members,
    remove_members,
    set_members,
)
from custom_components.spook.group_members import domains_a_group_holds

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _setup(hass: HomeAssistant) -> None:
    """Register the three actions on a running group integration."""
    assert await async_setup_component(hass, "group", {})
    for module in (add_members, remove_members, set_members):
        module.SpookService(hass).async_register()
    await hass.async_block_till_done()


async def _group(
    hass: HomeAssistant,
    members: list[str],
    *,
    hide_members: bool = False,
) -> MockConfigEntry:
    """Set up a light group holding the given members."""
    entry = MockConfigEntry(
        domain="group",
        title="Hallway",
        options={
            "group_type": "light",
            "name": "Hallway",
            "entities": members,
            "hide_members": hide_members,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _call(hass: HomeAssistant, service: str, **data: object) -> None:
    """Call one of the actions."""
    await hass.services.async_call("group", service, dict(data), blocking=True)


ENOUGH_GROUP_TYPES = 5


def _running(hass: HomeAssistant) -> list[str]:
    """Return the members the group Home Assistant is serving actually has."""
    return hass.states.get("light.hallway").attributes["entity_id"]


@pytest.fixture(autouse=True)
def _lights(hass: HomeAssistant) -> None:
    """Provide a few lights to move in and out of groups."""
    for name in ("one", "two", "three"):
        hass.states.async_set(f"light.{name}", "on")


async def test_adding_appends_and_the_group_follows(hass: HomeAssistant) -> None:
    """Test a new member lands at the end and reaches the running group."""
    await _setup(hass)
    entry = await _group(hass, ["light.one"])

    await _call(hass, "add_members", group="light.hallway", members=["light.two"])
    await hass.async_block_till_done()

    # Appended, not merged, so an order somebody arranged survives.
    assert entry.options["entities"] == ["light.one", "light.two"]
    assert _running(hass) == ["light.one", "light.two"]


async def test_adding_a_member_it_already_has_changes_nothing(
    hass: HomeAssistant,
) -> None:
    """Test asking twice does not list an entity twice."""
    await _setup(hass)
    entry = await _group(hass, ["light.one", "light.two"])

    await _call(
        hass, "add_members", group="light.hallway", members=["light.two", "light.three"]
    )
    await hass.async_block_till_done()

    assert entry.options["entities"] == ["light.one", "light.two", "light.three"]


async def test_adding_from_another_domain_is_refused(hass: HomeAssistant) -> None:
    """Test a light group is not given a switch to hold.

    A group of mixed domains reports nonsense rather than failing, so this is
    refused at the door instead of stored.
    """
    hass.states.async_set("switch.kettle", "on")
    await _setup(hass)
    entry = await _group(hass, ["light.one"])

    with pytest.raises(HomeAssistantError, match="holds light entities"):
        await _call(
            hass, "add_members", group="light.hallway", members=["switch.kettle"]
        )

    assert entry.options["entities"] == ["light.one"]


async def test_adding_something_that_does_not_exist_is_refused(
    hass: HomeAssistant,
) -> None:
    """Test Spook does not create work for its own repair.

    A member that does not exist is exactly what `group_unknown_members`
    reports, so putting one in would be Spook raising an issue about itself.
    """
    await _setup(hass)
    entry = await _group(hass, ["light.one"])

    with pytest.raises(HomeAssistantError, match=r"light\.nowhere"):
        await _call(
            hass, "add_members", group="light.hallway", members=["light.nowhere"]
        )

    assert entry.options["entities"] == ["light.one"]


async def test_removing_reaches_the_running_group(hass: HomeAssistant) -> None:
    """Test a member taken out is gone from the group being served."""
    await _setup(hass)
    entry = await _group(hass, ["light.one", "light.two"])

    await _call(hass, "remove_members", group="light.hallway", members=["light.two"])
    await hass.async_block_till_done()

    assert entry.options["entities"] == ["light.one"]
    assert _running(hass) == ["light.one"]


async def test_removing_takes_out_a_member_that_is_gone(hass: HomeAssistant) -> None:
    """Test the ghost case, which is the reason removal asks no questions."""
    await _setup(hass)
    entry = await _group(hass, ["light.one", "light.vanished"])

    await _call(
        hass, "remove_members", group="light.hallway", members=["light.vanished"]
    )
    await hass.async_block_till_done()

    assert entry.options["entities"] == ["light.one"]


async def test_removing_something_it_never_had_is_not_an_error(
    hass: HomeAssistant,
) -> None:
    """Test asking twice keeps working."""
    await _setup(hass)
    entry = await _group(hass, ["light.one"])

    await _call(hass, "remove_members", group="light.hallway", members=["light.two"])
    await hass.async_block_till_done()

    assert entry.options["entities"] == ["light.one"]


async def test_setting_replaces_and_drops_repeats(hass: HomeAssistant) -> None:
    """Test the list given is the list held, each entity once."""
    await _setup(hass)
    entry = await _group(hass, ["light.one"])

    await _call(
        hass,
        "set_members",
        group="light.hallway",
        members=["light.three", "light.two", "light.three"],
    )
    await hass.async_block_till_done()

    assert entry.options["entities"] == ["light.three", "light.two"]
    assert _running(hass) == ["light.three", "light.two"]


async def test_a_yaml_group_is_refused_and_told_where_to_go(
    hass: HomeAssistant,
) -> None:
    """Test the older kind of group says what does work on it.

    A group from YAML carries no unique ID, so it never reaches the entity
    registry. It still has a state, which is what separates it from a name
    somebody mistyped.
    """
    await _setup(hass)
    hass.states.async_set("group.living", "on", {"entity_id": ["light.one"]})

    with pytest.raises(HomeAssistantError, match=r"group\.set"):
        await _call(hass, "add_members", group="group.living", members=["light.two"])


async def test_an_entity_that_does_not_exist_is_refused(hass: HomeAssistant) -> None:
    """Test a mistyped group name says so."""
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match="Could not find entity_id"):
        await _call(hass, "add_members", group="light.nowhere", members=["light.two"])


async def test_something_that_is_not_a_group_is_refused(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a plain light is not treated as a group."""
    await _setup(hass)
    entity_registry.async_get_or_create("light", "demo", "bulb")

    with pytest.raises(HomeAssistantError, match="is not a group"):
        await _call(hass, "add_members", group="light.demo_bulb", members=["light.two"])


async def test_hiding_follows_the_members_in_and_out(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a group that hides its members keeps that promise.

    Left to the next reload, a member that just joined would still be on show
    and one that just left would stay hidden with nothing to explain why.
    """
    joining = entity_registry.async_get_or_create("light", "demo", "two")
    leaving = entity_registry.async_get_or_create(
        "light", "demo", "one", hidden_by=er.RegistryEntryHider.INTEGRATION
    )
    await _setup(hass)
    await _group(hass, [leaving.entity_id], hide_members=True)

    await _call(hass, "set_members", group="light.hallway", members=[joining.entity_id])
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(joining.entity_id).hidden_by
        is er.RegistryEntryHider.INTEGRATION
    )
    assert entity_registry.async_get(leaving.entity_id).hidden_by is None


async def test_hiding_leaves_what_somebody_hid_themselves(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a member hidden by hand stays hidden when it leaves.

    Somebody who hid an entity themselves meant it, and this action has no
    business undoing that. Core follows the same rule when a whole group is
    deleted.
    """
    entity_registry.async_get_or_create("light", "demo", "two")
    leaving = entity_registry.async_get_or_create(
        "light", "demo", "one", hidden_by=er.RegistryEntryHider.USER
    )
    await _setup(hass)
    await _group(hass, [leaving.entity_id], hide_members=True)

    await _call(hass, "set_members", group="light.hallway", members=["light.demo_two"])
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(leaving.entity_id).hidden_by
        is er.RegistryEntryHider.USER
    )


async def test_a_member_named_by_registry_id_is_accepted(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a group can be given a registry ID rather than an entity ID.

    That is a shape a group is allowed to hold, and it carries no domain of
    its own, so the checks have to resolve it before judging it.
    """
    joining = entity_registry.async_get_or_create("light", "demo", "two")
    await _setup(hass)
    entry = await _group(hass, ["light.one"])

    await _call(hass, "add_members", group="light.hallway", members=[joining.id])
    await hass.async_block_till_done()

    assert entry.options["entities"] == ["light.one", joining.id]


async def test_adding_the_same_entity_under_its_other_name_is_not_a_duplicate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test one entity cannot be in a group twice under two names.

    A group holds either an entity ID or a registry ID, whichever the
    interface had. Compared as strings the two names for one entity look like
    two entities, and the group would end up holding it twice.
    """
    existing = entity_registry.async_get_or_create("light", "demo", "one")
    await _setup(hass)
    entry = await _group(hass, [existing.id])

    await _call(
        hass, "add_members", group="light.hallway", members=[existing.entity_id]
    )
    await hass.async_block_till_done()

    assert entry.options["entities"] == [existing.id]


async def test_naming_one_entity_twice_in_a_call_adds_it_once(
    hass: HomeAssistant,
) -> None:
    """Test the check keeps up within a single call, not just against storage."""
    await _setup(hass)
    entry = await _group(hass, ["light.one"])

    await _call(
        hass,
        "add_members",
        group="light.hallway",
        members=["light.two", "light.two"],
    )
    await hass.async_block_till_done()

    assert entry.options["entities"] == ["light.one", "light.two"]


async def test_removing_works_through_the_other_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a member stored as a registry ID goes when named as an entity ID.

    Comparing the strings meant this reported success and left the member
    exactly where it was, which is the failure Spook is least willing to
    ship: a button that says it did something.
    """
    stored = entity_registry.async_get_or_create("light", "demo", "one")
    await _setup(hass)
    entry = await _group(hass, [stored.id, "light.two"])

    await _call(
        hass, "remove_members", group="light.hallway", members=[stored.entity_id]
    )
    await hass.async_block_till_done()

    assert entry.options["entities"] == ["light.two"]


async def test_setting_drops_two_names_for_one_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the first name given is kept and the second is dropped."""
    both = entity_registry.async_get_or_create("light", "demo", "one")
    await _setup(hass)
    entry = await _group(hass, ["light.two"])

    await _call(
        hass,
        "set_members",
        group="light.hallway",
        members=[both.entity_id, both.id],
    )
    await hass.async_block_till_done()

    assert entry.options["entities"] == [both.entity_id]


async def test_a_member_another_hiding_group_still_holds_stays_hidden(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test leaving one group does not undo what another group asked for.

    An entity can be in two groups, and either of them hiding its members is
    reason enough for it to stay out of the way. `hidden_by` records only
    that an integration did it, never which one, so the other groups have to
    be asked.
    """
    shared = entity_registry.async_get_or_create(
        "light", "demo", "one", hidden_by=er.RegistryEntryHider.INTEGRATION
    )
    entity_registry.async_get_or_create("light", "demo", "two")

    other = MockConfigEntry(
        domain="group",
        title="Landing",
        options={
            "group_type": "light",
            "name": "Landing",
            "entities": [shared.entity_id],
            "hide_members": True,
        },
    )
    other.add_to_hass(hass)

    await _setup(hass)
    await _group(hass, [shared.entity_id], hide_members=True)

    await _call(hass, "set_members", group="light.hallway", members=["light.demo_two"])
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(shared.entity_id).hidden_by
        is er.RegistryEntryHider.INTEGRATION
    )


async def test_a_plain_entity_is_not_mistaken_for_a_yaml_group(
    hass: HomeAssistant,
) -> None:
    """Test only the group domain gets pointed at `group.set`.

    An entity with a state and no registry entry is not automatically an old
    group; most of them belong to somebody else entirely. Telling their owner
    to go and edit their Lovelace groups would send them a long way off.
    """
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match="is not a group"):
        await _call(hass, "add_members", group="light.one", members=["light.two"])


async def test_a_sensor_group_takes_the_domains_the_dialog_offers(
    hass: HomeAssistant,
) -> None:
    """Test a sensor group holds numbers too, because core's dialog says so.

    It is not one domain per group. A sensor group offers `sensor`, `number`
    and `input_number`, and refusing the last two would mean these actions
    cannot build a group the interface builds happily.
    """
    hass.states.async_set("number.setpoint", "21", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.temperature", "20", {"unit_of_measurement": "°C"})
    await _setup(hass)

    entry = MockConfigEntry(
        domain="group",
        title="Warmth",
        options={
            "group_type": "sensor",
            "name": "Warmth",
            "entities": ["sensor.temperature"],
            "hide_members": False,
            "type": "max",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await _call(hass, "add_members", group="sensor.warmth", members=["number.setpoint"])
    await hass.async_block_till_done()

    assert entry.options["entities"] == ["sensor.temperature", "number.setpoint"]


async def test_a_sensor_group_still_refuses_a_light(hass: HomeAssistant) -> None:
    """Test widening the check did not turn it off."""
    await _setup(hass)

    hass.states.async_set("sensor.temperature", "20", {"unit_of_measurement": "°C"})
    entry = MockConfigEntry(
        domain="group",
        title="Warmth",
        options={
            "group_type": "sensor",
            "name": "Warmth",
            "entities": ["sensor.temperature"],
            "hide_members": False,
            "type": "max",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match="input_number, number, sensor"):
        await _call(hass, "add_members", group="sensor.warmth", members=["light.one"])


def test_every_group_type_reports_the_domains_it_holds() -> None:
    """Guard the one assumption about the shape of somebody else's flow.

    The allowed domains are read out of core's own config flow. If that moves,
    the reading returns nothing and the domain check silently stops happening,
    which is a quiet loss rather than a loud one. This is the loud one.

    Needs nothing running: it is a question about the shape of two modules.
    """
    checked = 0
    for group_type, step in GroupConfigFlowHandler.config_flow.items():
        if not hasattr(step, "schema"):
            # The menu step that asks which kind of group to make.
            continue
        domains = domains_a_group_holds(group_type)
        assert domains, f"no domains found for a {group_type} group"
        assert group_type in domains
        checked += 1

    assert checked > ENOUGH_GROUP_TYPES, "the walk stopped finding group types"
    assert domains_a_group_holds("sensor") == {"sensor", "number", "input_number"}


async def test_a_member_the_user_hid_is_never_claimed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test joining does not write over somebody's own choice.

    Claiming it would look harmless, since it is hidden either way. The
    damage shows up later: on the way out this would see its own mark and put
    the entity back on show, which is exactly what it must not do.
    """
    theirs = entity_registry.async_get_or_create(
        "light", "demo", "two", hidden_by=er.RegistryEntryHider.USER
    )
    entity_registry.async_get_or_create("light", "demo", "one")
    await _setup(hass)
    await _group(hass, ["light.demo_one"], hide_members=True)

    await _call(hass, "set_members", group="light.hallway", members=[theirs.entity_id])
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(theirs.entity_id).hidden_by
        is er.RegistryEntryHider.USER
    )

    # And out again: still theirs, still hidden.
    await _call(hass, "set_members", group="light.hallway", members=["light.demo_one"])
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(theirs.entity_id).hidden_by
        is er.RegistryEntryHider.USER
    )
