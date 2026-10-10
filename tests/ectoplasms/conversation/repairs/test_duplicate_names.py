"""Tests for the repair that finds names Assist cannot tell apart."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.conversation.repairs import duplicate_names
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        area_registry as ar,
        device_registry as dr,
        issue_registry as ir,
    )


async def _set_up_assist(hass: HomeAssistant) -> None:
    """Set up exposure settings, and pretend Assist is loaded.

    Conversation itself needs hassil, which the tests do not have. The
    repair only asks whether it is loaded, and everything it matches with
    lives in core's helpers.
    """
    assert await async_setup_component(hass, "homeassistant", {})
    hass.config.components.add("conversation")


def _entity(  # noqa: PLR0913 # pylint: disable=too-many-arguments
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    object_id: str,
    name: str,
    *,
    domain: str = "light",
    area_id: str | None = None,
    aliases: list[str | er.ComputedNameType] | None = None,
    exposed: bool = True,
    device_id: str | None = None,
) -> str:
    """Add an entity with a state, in an area, exposed to Assist or not."""
    entry = entity_registry.async_get_or_create(
        domain,
        "test",
        object_id,
        suggested_object_id=object_id,
        original_name=name,
        device_id=device_id,
    )
    if area_id is not None or aliases is not None:
        entity_registry.async_update_entity(
            entry.entity_id,
            area_id=area_id,
            aliases=aliases if aliases is not None else [er.COMPUTED_NAME],
        )
    hass.states.async_set(entry.entity_id, "on", {"friendly_name": name})
    async_expose_entity(hass, "conversation", entry.entity_id, should_expose=exposed)
    return entry.entity_id


async def _inspect(hass: HomeAssistant) -> duplicate_names.SpookRepair:
    """Run one inspection of the repair."""
    repair = duplicate_names.SpookRepair(hass)
    await repair.async_inspect()
    return repair


def _issue(issue_registry: ir.IssueRegistry, slug: str = "lamp") -> ir.IssueEntry:
    """Return the issue about a name, failing when there is none."""
    issue = async_issue_about(issue_registry, f"assist_duplicate_names_{slug}")
    assert issue
    return issue


def _no_issues(issue_registry: ir.IssueRegistry) -> bool:
    """Return whether the repair raised nothing at all."""
    return not [
        issue_id
        for _, issue_id in issue_registry.issues
        if issue_id.startswith("assist_duplicate_names_")
    ]


async def test_same_name_in_the_same_area_is_reported(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Naming the area still leaves two, so Assist gives up."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=kitchen.id)
    _entity(hass, entity_registry, "lamp_2", "Lamp", area_id=kitchen.id)

    await _inspect(hass)

    issue = _issue(issue_registry)
    assert issue.issue_domain == "conversation"
    assert not issue.is_fixable
    assert issue.translation_key == "assist_duplicate_names"
    assert issue.translation_placeholders == {
        "name": "Lamp",
        "entities": "- `light.lamp_1` (Kitchen)\n- `light.lamp_2` (Kitchen)",
    }


async def test_same_name_in_different_areas_is_left_alone(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The area tells them apart, so Assist copes on its own."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    bedroom = area_registry.async_create("Bedroom")
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=kitchen.id)
    _entity(hass, entity_registry, "lamp_2", "Lamp", area_id=bedroom.id)

    await _inspect(hass)

    assert _no_issues(issue_registry)


async def test_same_name_without_any_area_is_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Nothing to tell them apart by, not even an area to name."""
    await _set_up_assist(hass)
    _entity(hass, entity_registry, "lamp_1", "Lamp")
    _entity(hass, entity_registry, "lamp_2", "Lamp")

    await _inspect(hass)

    assert _issue(issue_registry).translation_placeholders == {
        "name": "Lamp",
        "entities": "- `light.lamp_1`\n- `light.lamp_2`",
    }


async def test_one_without_an_area_is_reported(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The one in an area can be asked for, the one without never can."""
    await _set_up_assist(hass)
    bedroom = area_registry.async_create("Bedroom")
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=bedroom.id)
    _entity(hass, entity_registry, "lamp_2", "Lamp")

    await _inspect(hass)

    assert _issue(issue_registry).translation_placeholders == {
        "name": "Lamp",
        "entities": "- `light.lamp_1` (Bedroom)\n- `light.lamp_2`",
    }


async def test_an_entity_not_exposed_is_never_judged(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Assist does not know it exists, so it is not in the way."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=kitchen.id)
    _entity(hass, entity_registry, "lamp_2", "Lamp", area_id=kitchen.id, exposed=False)

    await _inspect(hass)

    assert _no_issues(issue_registry)


async def test_case_and_surrounding_spaces_do_not_count(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Assist compares names stripped and casefolded."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=kitchen.id)
    _entity(
        hass,
        entity_registry,
        "lamp_2",
        "lamp",
        area_id=kitchen.id,
        aliases=["  LAMP  "],
    )

    await _inspect(hass)

    assert _issue(issue_registry).translation_placeholders == {
        "name": "LAMP",
        "entities": "- `light.lamp_1` (Kitchen)\n- `light.lamp_2` (Kitchen)",
    }


async def test_names_that_differ_after_normalizing_are_left_alone(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Close is not the same: Assist matches the whole name."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=kitchen.id)
    _entity(hass, entity_registry, "lamp_2", "Lamp 2", area_id=kitchen.id)

    await _inspect(hass)

    assert _no_issues(issue_registry)


async def test_an_alias_colliding_with_a_name_is_reported(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An alias is a name to Assist like any other."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    _entity(hass, entity_registry, "lamp", "Lamp", area_id=kitchen.id)
    _entity(
        hass,
        entity_registry,
        "ceiling",
        "Ceiling",
        area_id=kitchen.id,
        aliases=[er.COMPUTED_NAME, "Lamp"],
    )

    await _inspect(hass)

    assert _issue(issue_registry).translation_placeholders == {
        "name": "Lamp",
        "entities": "- `light.ceiling` (Kitchen)\n- `light.lamp` (Kitchen)",
    }


async def test_a_name_left_out_of_the_aliases_is_not_one(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Without the computed name in its aliases, Assist does not hear it."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=kitchen.id)
    _entity(
        hass,
        entity_registry,
        "lamp_2",
        "Lamp",
        area_id=kitchen.id,
        aliases=["Reading light"],
    )

    await _inspect(hass)

    assert _no_issues(issue_registry)


async def test_a_name_nobody_can_say_is_left_alone(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Assist drops a name that is only punctuation, so it collides with nothing."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    _entity(
        hass,
        entity_registry,
        "lamp_1",
        "Lamp",
        area_id=kitchen.id,
        aliases=[er.COMPUTED_NAME, "..."],
    )
    _entity(
        hass,
        entity_registry,
        "lamp_2",
        "Bulb",
        area_id=kitchen.id,
        aliases=[er.COMPUTED_NAME, "..."],
    )

    await _inspect(hass)

    assert _no_issues(issue_registry)


async def test_the_area_of_the_device_counts(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An entity without an area of its own is where its device is."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    bedroom = area_registry.async_create("Bedroom")
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "plug")},
        name="Plug",
    )
    device_registry.async_update_device(device.id, area_id=bedroom.id)
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=kitchen.id)
    _entity(
        hass,
        entity_registry,
        "lamp_2",
        "Lamp",
        domain="switch",
        device_id=device.id,
        # Named outright: the computed name would put the device in front.
        aliases=["Lamp"],
    )

    await _inspect(hass)

    assert _no_issues(issue_registry)

    # Move the device into the kitchen, and the two are in one area.
    device_registry.async_update_device(device.id, area_id=kitchen.id)
    await _inspect(hass)

    assert _issue(issue_registry).translation_placeholders == {
        "name": "Lamp",
        "entities": "- `light.lamp_1` (Kitchen)\n- `switch.lamp_2` (Kitchen)",
    }


async def test_a_device_name_counts_through_its_entity(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An entity named after its device answers to the device's name."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    for number in (1, 2):
        device = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("test", f"plug_{number}")},
            name="Smart plug",
        )
        device_registry.async_update_device(device.id, area_id=kitchen.id)
        entry = entity_registry.async_get_or_create(
            "switch",
            "test",
            f"plug_{number}",
            suggested_object_id=f"plug_{number}",
            device_id=device.id,
            has_entity_name=True,
            original_name=None,
        )
        hass.states.async_set(entry.entity_id, "on")
        async_expose_entity(hass, "conversation", entry.entity_id, should_expose=True)

    await _inspect(hass)

    assert _issue(issue_registry, "smart_plug").translation_placeholders == {
        "name": "Smart plug",
        "entities": "- `switch.plug_1` (Kitchen)\n- `switch.plug_2` (Kitchen)",
    }


async def test_one_alone_in_its_area_still_shows_up_in_the_list(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Two share the kitchen, the third answers to the same name elsewhere."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    bedroom = area_registry.async_create("Bedroom")
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=kitchen.id)
    _entity(hass, entity_registry, "lamp_2", "Lamp", area_id=kitchen.id)
    _entity(hass, entity_registry, "lamp_3", "Lamp", area_id=bedroom.id)

    await _inspect(hass)

    assert _issue(issue_registry).translation_placeholders == {
        "name": "Lamp",
        "entities": (
            "- `light.lamp_1` (Kitchen)\n"
            "- `light.lamp_2` (Kitchen)\n"
            "- `light.lamp_3` (Bedroom)"
        ),
    }


async def test_an_entity_without_a_unique_id_counts(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Assist knows it by the name of its state, and it can have no area."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=kitchen.id)
    hass.states.async_set("light.yaml_lamp", "on", {"friendly_name": "Lamp"})
    async_expose_entity(hass, "conversation", "light.yaml_lamp", should_expose=True)

    await _inspect(hass)

    assert _issue(issue_registry).translation_placeholders == {
        "name": "Lamp",
        "entities": "- `light.lamp_1` (Kitchen)\n- `light.yaml_lamp`",
    }


async def test_nothing_is_judged_without_assist(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Without conversation loaded, nobody asks for anything by name."""
    assert await async_setup_component(hass, "homeassistant", {})
    _entity(hass, entity_registry, "lamp_1", "Lamp")
    _entity(hass, entity_registry, "lamp_2", "Lamp")

    await _inspect(hass)

    assert _no_issues(issue_registry)


async def test_the_issue_goes_once_the_name_is_changed(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Renaming one of them is the fix, and the next look sees it."""
    await _set_up_assist(hass)
    kitchen = area_registry.async_create("Kitchen")
    _entity(hass, entity_registry, "lamp_1", "Lamp", area_id=kitchen.id)
    _entity(hass, entity_registry, "lamp_2", "Lamp", area_id=kitchen.id)
    repair = duplicate_names.SpookRepair(hass)
    await repair.async_inspect()
    assert _issue(issue_registry)

    entity_registry.async_update_entity("light.lamp_2", name="Reading lamp")
    # pylint: disable-next=protected-access
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert _no_issues(issue_registry)


async def test_a_change_in_exposure_brings_a_look(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Hiding an entity from Assist can be the fix, and is heard as one."""
    await _set_up_assist(hass)
    _entity(hass, entity_registry, "lamp_1", "Lamp")
    hass.states.async_set("light.yaml_lamp", "on", {"friendly_name": "Lamp"})
    async_expose_entity(hass, "conversation", "light.yaml_lamp", should_expose=True)

    repair = duplicate_names.SpookRepair(hass)
    await repair.async_activate()
    # Listening starts with the first look that finds Assist, and only once.
    await repair.async_inspect()
    await repair.async_inspect()
    calls: list[None] = []
    repair.inspect_debouncer.async_schedule_call = lambda: calls.append(None)

    # Kept outside the entity registry, so no registry event follows it.
    async_expose_entity(hass, "conversation", "light.yaml_lamp", should_expose=False)

    assert len(calls) == 1
    await repair.async_deactivate()
