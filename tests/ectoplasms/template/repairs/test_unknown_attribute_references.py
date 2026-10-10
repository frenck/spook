"""Tests for the template helper unknown attribute references repair."""

# The cleanup round is what an issue keyed to its findings needs looking at,
# and there is no public way to it.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from homeassistant.util import dt as dt_util

from custom_components.spook import attribute_checking
from custom_components.spook.ectoplasms.template.repairs import (
    unknown_attribute_references,
)
from custom_components.spook.ectoplasms.template.repairs.unknown_attribute_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er, issue_registry as ir

PREFIX = "template_unknown_attribute_references"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_db_url: str,
    enable_custom_integrations: None,
) -> None:
    """Prepare the recorder's database before Home Assistant starts.

    The recorder fixtures insist on going first, and the shared fixture that
    enables custom integrations starts Home Assistant.
    """
    _ = recorder_db_url, enable_custom_integrations


def _sensor(hass: HomeAssistant, state: str, **extra: Any) -> MockConfigEntry:
    """Add a template sensor helper, the way the UI stores one."""
    entry = MockConfigEntry(
        domain="template",
        title="Haunted",
        options={
            "name": "Haunted",
            "template_type": "sensor",
            "state": state,
            **extra,
        },
    )
    entry.add_to_hass(hass)
    return entry


def _switch(hass: HomeAssistant, turn_on: list[dict[str, Any]]) -> MockConfigEntry:
    """Add a template switch helper with actions, the way the UI stores one."""
    entry = MockConfigEntry(
        domain="template",
        title="Haunted switch",
        options={
            "name": "Haunted switch",
            "template_type": "switch",
            "value_template": "{{ is_state('light.kitchen', 'on') }}",
            "turn_on": turn_on,
            "turn_off": [],
        },
    )
    entry.add_to_hass(hass)
    return entry


def _brightness_condition(attribute: str, **extra: Any) -> dict[str, Any]:
    """Return a state condition on an attribute of the kitchen light."""
    return {
        "condition": "state",
        "entity_id": "light.kitchen",
        "attribute": attribute,
        "state": "255",
        **extra,
    }


def _issue(
    issue_registry: ir.IssueRegistry, entry: MockConfigEntry
) -> ir.IssueEntry | None:
    """Return the issue about a helper, if there is one."""
    return async_issue_about(issue_registry, f"{PREFIX}_{entry.entry_id}")


async def test_case_only_is_reported_without_a_recorder(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a difference in case alone is reported, recorder or not."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'Brightness') }}")

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, entry)
    assert issue
    assert issue.translation_key == PREFIX
    assert issue.issue_domain == "template"
    assert (
        issue.learn_more_url
        == "https://spook.boo/template#unknown-referenced-attributes"
    )
    assert issue.translation_placeholders == {
        "attributes": (
            "- `Brightness` of `light.kitchen` (did you mean `brightness`?)"
        ),
        "helper": "Haunted",
        "edit": "/config/helpers",
        "entity_id": entry.entry_id,
    }


async def test_names_the_entities_the_helper_registered(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the issue names the helper by what it registered, when it did."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'Brightness') }}")
    entity_registry.async_get_or_create(
        "sensor",
        "template",
        entry.entry_id,
        config_entry=entry,
        suggested_object_id="haunted",
    )

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, entry)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["entity_id"] == "sensor.haunted"


async def test_without_a_recorder_only_case_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute nobody can rule out is not reported without history."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'wobble') }}")

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, entry) is None


async def test_known_attribute_is_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute the entity has right now is not reported."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'brightness') }}")

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, entry) is None


async def test_entity_without_a_state_is_passed_over(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entity that is not there says nothing about its attributes.

    Whether it exists is the unknown entity repair's business.
    """
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'Brightness') }}")

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, entry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_never_had_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute the entity never had is reported, from history."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255, "glow": 1})
    await async_wait_recording_done(hass)
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'wobble') }}")

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, entry)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["attributes"] == (
        "- `wobble` of `light.kitchen`"
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_only_in_history_is_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute the entity had once, and not right now, is fine.

    The later state carries attributes of its own: a state without any is
    stored as an empty set, and that makes the history not whole, which
    would keep the attribute from being reported for another reason.
    """
    hass.states.async_set("light.kitchen", "on", {"wobble": 1})
    hass.states.async_set("light.kitchen", "off", {"brightness": 255})
    await async_wait_recording_done(hass)
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'wobble') }}")

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, entry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_custom_attribute_present_now_is_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an attribute an integration adds of its own is fine while there.

    Even when the recorder has never seen it, which is what it says here.
    """

    def _never_seen_it(_hass: HomeAssistant, entity_ids: list[str]) -> dict:
        return {entity_id: ({"brightness"}, True) for entity_id in entity_ids}

    monkeypatch.setattr(
        attribute_checking, "_read_recorded_attribute_keys", _never_seen_it
    )
    hass.states.async_set("light.kitchen", "on", {"wobble": 1})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'wobble') }}")

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, entry) is None


@pytest.mark.parametrize(
    "options",
    [
        {"state": "{{ states.light.kitchen.attributes.Brightness }}"},
        {"state": "{{ is_state_attr('light.kitchen', 'Brightness', 255) }}"},
        {"state": "{{ 'light.kitchen' | state_attr('Brightness') }}"},
        {
            "state": "{{ 1 }}",
            "availability": "{{ state_attr('light.kitchen', 'Brightness') }}",
        },
        {
            "state": "{{ 1 }}",
            "additional_options": {
                "availability": "{{ state_attr('light.kitchen', 'Brightness') }}"
            },
        },
        {"state": "{{ 1 }}", "name": "{{ state_attr('light.kitchen', 'Brightness') }}"},
    ],
    ids=[
        "states object",
        "is_state_attr",
        "filter",
        "availability",
        "availability under additional options",
        "name",
    ],
)
async def test_every_template_of_the_options_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    options: dict[str, Any],
) -> None:
    """Test each template the helper renders is read, wherever it is kept."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = MockConfigEntry(
        domain="template",
        title="Haunted",
        options={"name": "Haunted", "template_type": "sensor", **options},
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, entry)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["attributes"] == (
        "- `Brightness` of `light.kitchen` (did you mean `brightness`?)"
    )


@pytest.mark.parametrize(
    "turn_on",
    [
        [_brightness_condition("Brightness")],
        [
            {
                "if": [_brightness_condition("Brightness")],
                "then": [{"action": "light.turn_on", "target": {"entity_id": "all"}}],
            }
        ],
        [
            {
                "wait_for_trigger": [
                    {
                        "trigger": "state",
                        "entity_id": "light.kitchen",
                        "attribute": "Brightness",
                    }
                ]
            }
        ],
        [
            {
                "action": "light.turn_on",
                "data": {
                    "brightness": "{{ state_attr('light.kitchen', 'Brightness') }}"
                },
            }
        ],
    ],
    ids=["condition step", "nested condition", "wait for a trigger", "action data"],
)
async def test_actions_are_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    turn_on: list[dict[str, Any]],
) -> None:
    """Test the actions of a helper are read like those of a script."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _switch(hass, turn_on)

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, entry)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["attributes"] == (
        "- `Brightness` of `light.kitchen` (did you mean `brightness`?)"
    )


async def test_registry_id_in_an_action_is_resolved(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a condition naming its entity by registry ID is checked too.

    That is what the editor writes in some places.
    """
    registered = entity_registry.async_get_or_create(
        "light", "demo", "kitchen", suggested_object_id="kitchen"
    )
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _switch(
        hass, [_brightness_condition("Brightness", entity_id=registered.id)]
    )

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, entry)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["attributes"] == (
        "- `Brightness` of `light.kitchen` (did you mean `brightness`?)"
    )


async def test_spook_state_trigger_in_an_action_is_followed(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the entities Spook's own trigger watches are checked."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _switch(
        hass,
        [
            {
                "wait_for_trigger": [
                    {
                        "trigger": "spook.state_changed",
                        "target": {"entity_id": ["light.kitchen"]},
                        "options": {"attribute": "Brightness"},
                    }
                ]
            }
        ],
    )

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, entry)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["attributes"] == (
        "- `Brightness` of `light.kitchen` (did you mean `brightness`?)"
    )


@pytest.mark.parametrize(
    "turn_on",
    [
        [_brightness_condition("Brightness", enabled=False)],
        [
            {
                "variables": {"state_attr": 1},
            },
            {
                "action": "light.turn_on",
                "data": {
                    "brightness": "{{ state_attr('light.kitchen', 'Brightness') }}"
                },
            },
        ],
        [
            {
                "action": "light.turn_on",
                "alias": "{{ state_attr('light.kitchen', 'Brightness') }}",
            }
        ],
        [_brightness_condition("{{ which }}")],
    ],
    ids=[
        "disabled step",
        "own name for state_attr",
        "never rendered",
        "templated attribute",
    ],
)
async def test_what_cannot_break_anything_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    turn_on: list[dict[str, Any]],
) -> None:
    """Test what does nothing, or is not Home Assistant's lookup, is not read."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _switch(hass, turn_on)

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, entry) is None


async def test_one_issue_per_helper(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test each helper gets an issue of its own, with only its own findings."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    hass.states.async_set("light.hallway", "on", {"color_temp": 300})
    kitchen = _sensor(hass, "{{ state_attr('light.kitchen', 'Brightness') }}")
    hallway = _sensor(hass, "{{ state_attr('light.hallway', 'Color_Temp') }}")

    await SpookRepair(hass).async_inspect()

    kitchen_issue = _issue(issue_registry, kitchen)
    hallway_issue = _issue(issue_registry, hallway)
    assert kitchen_issue
    assert kitchen_issue.translation_placeholders
    assert kitchen_issue.translation_placeholders["attributes"] == (
        "- `Brightness` of `light.kitchen` (did you mean `brightness`?)"
    )
    assert hallway_issue
    assert hallway_issue.translation_placeholders
    assert hallway_issue.translation_placeholders["attributes"] == (
        "- `Color_Temp` of `light.hallway` (did you mean `color_temp`?)"
    )


async def test_findings_are_listed_in_order(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test several findings of one helper are listed by entity, then name."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255, "hs_color": 1})
    hass.states.async_set("light.hallway", "on", {"color_temp": 300})
    entry = _sensor(
        hass,
        "{{ state_attr('light.kitchen', 'Hs_Color') }}"
        "{{ state_attr('light.kitchen', 'Brightness') }}"
        "{{ state_attr('light.hallway', 'Color_Temp') }}",
    )

    await SpookRepair(hass).async_inspect()

    issue = _issue(issue_registry, entry)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["attributes"] == (
        "- `Color_Temp` of `light.hallway` (did you mean `color_temp`?)\n"
        "- `Brightness` of `light.kitchen` (did you mean `brightness`?)\n"
        "- `Hs_Color` of `light.kitchen` (did you mean `hs_color`?)"
    )


async def test_fixed_is_cleared(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue goes once the helper is changed to a real attribute.

    Also what the repair remembers of a helper: changed options are read
    again, not taken from the last round.
    """
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'Brightness') }}")

    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, entry)

    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "state": "{{ state_attr('light.kitchen', 'brightness') }}",
        },
    )
    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, entry) is None


async def test_removed_helper_is_cleared(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue goes with the helper."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'Brightness') }}")

    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, entry)

    await hass.config_entries.async_remove(entry.entry_id)
    await repair._async_inspect_with_cleanup()
    assert _issue(issue_registry, entry) is None


def _meanwhile(monkeypatch: pytest.MonkeyPatch, happens: Any) -> None:
    """Make something happen while the recorder is being asked."""
    ask = unknown_attribute_references.async_unknown_attributes

    async def _asking(
        hass: HomeAssistant, pairs: Iterable[tuple[str, str]]
    ) -> set[attribute_checking.UnknownAttribute]:
        found = await ask(hass, pairs)
        await happens()
        return found

    monkeypatch.setattr(
        unknown_attribute_references, "async_unknown_attributes", _asking
    )


async def test_helper_changed_while_asking_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a helper fixed while the recorder was asked is not reported.

    What was found is about options it no longer has. Changing it starts
    another round, which looks at the new ones.
    """
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'Brightness') }}")

    async def _fixed() -> None:
        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                "state": "{{ state_attr('light.kitchen', 'brightness') }}",
            },
        )

    _meanwhile(monkeypatch, _fixed)

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, entry) is None


async def test_helper_removed_while_asking_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a helper removed while the recorder was asked is not reported."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'Brightness') }}")

    async def _removed() -> None:
        await hass.config_entries.async_remove(entry.entry_id)

    _meanwhile(monkeypatch, _removed)

    await SpookRepair(hass).async_inspect()

    assert _issue(issue_registry, entry) is None


async def test_not_before_the_recorder_settles(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test nothing is looked at until a while after starting.

    Not even when something that would normally make it look happens.
    """
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'Brightness') }}")

    repair = SpookRepair(hass)
    await repair.async_activate()

    hass.bus.async_fire("component_loaded", {"component": "light"})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=9))
    await hass.async_block_till_done()
    assert _issue(issue_registry, entry) is None

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10, seconds=1))
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10, seconds=5))
    await hass.async_block_till_done()
    assert _issue(issue_registry, entry)

    await repair.async_deactivate()


async def _settled(hass: HomeAssistant) -> SpookRepair:
    """Return an active repair past its first look."""
    repair = SpookRepair(hass)
    await repair.async_activate()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10, seconds=1))
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10, seconds=5))
    await hass.async_block_till_done()
    return repair


async def _debounced(hass: HomeAssistant) -> None:
    """Let the debouncer of the repair run what was asked of it."""
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=11))
    await hass.async_block_till_done()


async def test_looks_again_when_a_helper_changes(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test changing a template helper makes it look again."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'brightness') }}")
    repair = await _settled(hass)
    assert _issue(issue_registry, entry) is None

    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "state": "{{ state_attr('light.kitchen', 'Brightness') }}",
        },
    )
    await _debounced(hass)
    assert _issue(issue_registry, entry)

    await repair.async_deactivate()


async def test_looks_again_when_an_entity_shows_up(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entity that shows up later is looked at once it is there.

    Until then it has no state, and it is passed over.
    """
    entry = _sensor(hass, "{{ state_attr('light.kitchen', 'Brightness') }}")
    repair = await _settled(hass)
    assert _issue(issue_registry, entry) is None

    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    await _debounced(hass)
    assert _issue(issue_registry, entry)

    await repair.async_deactivate()
