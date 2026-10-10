"""Tests for attribute values in the automation unknown state references repair."""

# pylint: disable=wrong-import-order,protected-access
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)
from sqlalchemy import update
from sqlalchemy.exc import OperationalError

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.light import LightEntity
from homeassistant.components.recorder.db_schema import StateAttributes
from homeassistant.helpers.recorder import get_instance, session_scope
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook import attribute_checking, attribute_value_checking
from custom_components.spook.attribute_value_checking import (
    DATA_ATTRIBUTE_VALUE_KNOWLEDGE,
    DATA_ATTRIBUTE_VALUES,
)
from custom_components.spook.ectoplasms.automation.repairs.unknown_state_references import (
    SpookRepair,
)
from tests.entity_objects import give_entity_objects
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "automation_unknown_state_references_automation.haunted"
CLIMATE = "climate.living_room"


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


async def _automation(
    hass: HomeAssistant,
    *,
    triggers: list[dict[str, Any]] | None = None,
    conditions: list[dict[str, Any]] | None = None,
) -> None:
    """Set up the haunted automation with these triggers and conditions."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "triggers": triggers
                    or [{"trigger": "event", "event_type": "nothing"}],
                    "conditions": conditions or [],
                    "actions": [],
                }
            ]
        },
    )
    await hass.async_block_till_done()


def _attribute_trigger(attribute: str, **values: Any) -> dict[str, Any]:
    """Return a state trigger on an attribute of the climate entity."""
    return {"trigger": "state", "entity_id": CLIMATE, "attribute": attribute, **values}


async def _climate(hass: HomeAssistant, *attribute_sets: dict[str, Any]) -> None:
    """Make the climate entity core's own, give it each set, let it be recorded."""
    give_entity_objects(hass, CLIMATE, kind=ClimateEntity)
    for attributes in attribute_sets:
        hass.states.async_set(CLIMATE, "heat", attributes)
    await async_wait_recording_done(hass)


def _found(issue_registry: ir.IssueRegistry) -> str | None:
    """Return what the issue lists, if there is one."""
    if (issue := async_issue_about(issue_registry, ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["states"]


# What is reported.


@pytest.mark.usefixtures("recorder_mock")
async def test_case_only_is_reported_with_history(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a value of a fixed set in another case is reported.

    `Heating` is never an `hvac_action`: core's own enum says `heating`.
    """
    await _climate(hass, {"hvac_action": "idle"})
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) == (
        "- `hvac_action` of `climate.living_room`: `Heating` (did you mean `heating`?)"
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("to", "Heating"),
        ("from", "Heating"),
        ("not_to", "Heating"),
        ("to", ["Heating"]),
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_every_trigger_option_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    key: str,
    value: Any,
) -> None:
    """Test every option of the trigger that names a value is read."""
    await _climate(hass, {"hvac_action": "idle"})
    await _automation(
        hass, triggers=[_attribute_trigger("hvac_action", **{key: value})]
    )

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry)


@pytest.mark.usefixtures("recorder_mock")
async def test_condition_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the `state` of a state condition with an attribute is read."""
    await _climate(hass, {"hvac_action": "idle"})
    await _automation(
        hass,
        conditions=[
            {
                "condition": "state",
                "entity_id": CLIMATE,
                "attribute": "hvac_action",
                "state": "Heating",
            }
        ],
    )

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) == (
        "- `hvac_action` of `climate.living_room`: `Heating` (did you mean `heating`?)"
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_yaml_boolean_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an unquoted `off`, which YAML reads as false, is reported.

    Core compares the attribute with the boolean, and `off` is never false.
    """
    await _climate(hass, {"hvac_action": "idle"})
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to=False)])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) == (
        '- `hvac_action` of `climate.living_room`: `false` (did you mean `"off"`?)'
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_suggestion_is_quoted_when_yaml_would_not_keep_it_text(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a quoted `Off` gets `"off"` suggested, quotes and all.

    Copied as `off` without quotes, YAML makes it false, which never matches
    either.
    """
    await _climate(hass, {"hvac_action": "idle"})
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Off")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) == (
        '- `hvac_action` of `climate.living_room`: `Off` (did you mean `"off"`?)'
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_yaml_number_is_reported_against_options(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a fan mode written as a number, where the modes are text, is reported."""
    await _climate(hass, {"fan_modes": ["1", "2"], "fan_mode": "1"})
    await _automation(hass, triggers=[_attribute_trigger("fan_mode", to=2)])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) == (
        '- `fan_mode` of `climate.living_room`: `2` (did you mean `"2"`?)'
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_option_in_another_case_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a value the entity offers for the attribute, in another case."""
    await _climate(hass, {"preset_modes": ["eco", "comfort"], "preset_mode": "eco"})
    await _automation(hass, triggers=[_attribute_trigger("preset_mode", to="Comfort")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) == (
        "- `preset_mode` of `climate.living_room`: `Comfort` (did you mean `comfort`?)"
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_states_and_values_share_one_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the states and attribute values of an automation are one list."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "off")
    await _climate(hass, {"hvac_action": "idle"})
    await _automation(
        hass,
        triggers=[
            {"trigger": "state", "entity_id": "light.kitchen", "to": "On"},
            _attribute_trigger("hvac_action", to="Heating"),
        ],
    )

    await SpookRepair(hass).async_inspect()

    # In the order of their entities.
    assert _found(issue_registry) == (
        "- `hvac_action` of `climate.living_room`: `Heating` (did you mean `heating`?)\n"
        "- `On` for `light.kitchen` (did you mean `on`?)"
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_draft_check_names_the_attribute(hass: HomeAssistant) -> None:
    """Test a draft gets the attribute value back with the attribute it is of."""
    await _climate(hass, {"hvac_action": "idle"})
    draft = SimpleNamespace(
        entity_id="automation.draft",
        raw_config={"triggers": [_attribute_trigger("hvac_action", to=False)]},
    )

    assert await SpookRepair(hass).async_check_draft(draft) == [
        'hvac_action of climate.living_room: false (did you mean "off"?)'
    ]


# What is not reported.


async def test_nothing_without_a_recorder(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a case slip needs the whole history: core does not keep the set.

    An integration can write `Heating` as its hvac action, and only history
    can say this one never did.
    """
    give_entity_objects(hass, CLIMATE, kind=ClimateEntity)
    hass.states.async_set(CLIMATE, "heat", {"hvac_action": "idle"})
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_value_in_history_is_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a value the attribute once had, in any case, is fine."""
    await _climate(hass, {"hvac_action": "Heating"}, {"hvac_action": "idle"})
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_boolean_in_history_is_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a boolean the attribute once had is fine, written as a boolean."""
    await _climate(hass, {"hvac_action": False}, {"hvac_action": "idle"})
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to=False)])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_value_outside_of_the_set_is_not_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a value that is no slip of a known one is never reported.

    Core does not keep the set, so an integration can have its own word.
    """
    await _climate(hass, {"hvac_action": "idle"})
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="warming")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_boolean_is_no_slip_of_a_number(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test `true` is not taken for `1`: YAML never reads `1` as a boolean."""
    await _climate(hass, {"fan_modes": ["1", "2"], "fan_mode": "1"})
    await _automation(hass, triggers=[_attribute_trigger("fan_mode", to=True)])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_never_had_is_left_to_the_attribute_repair(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test values of an attribute the entity never had are not judged.

    That the attribute is not there is the finding, and another repair's.
    """
    await _climate(hass, {"current_temperature": 20})
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_unrecorded_attribute_is_not_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute the recorder leaves out has no history to go by."""
    give_entity_objects(hass, CLIMATE, kind=ClimateEntity)
    hass.states.async_set(
        CLIMATE,
        "heat",
        {"hvac_action": "idle", "current_temperature": 20},
        state_info={"unrecorded_attributes": frozenset({"hvac_action"})},
    )
    await async_wait_recording_done(hass)
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_set_from_outside_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entity whose state its integration did not set is not judged."""
    hass.states.async_set(CLIMATE, "heat", {"hvac_action": "idle"})
    await async_wait_recording_done(hass)
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_without_a_fixed_set_is_not_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute that can be anything is not judged, history or not."""
    await _climate(hass, {"hvac_action": "idle", "mood": "calm"})
    await _automation(hass, triggers=[_attribute_trigger("mood", to="Calm")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_options_gone_means_not_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute checked by its options is not, once it offers none.

    Whether it is checked is down to what the entity is right now.
    """
    await _climate(
        hass,
        {"fan_modes": ["low", "high"], "fan_mode": "low"},
        {"fan_mode": "low"},
    )
    await _automation(hass, triggers=[_attribute_trigger("fan_mode", to="Low")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_more_history_than_is_read_is_not_whole(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an entity with more attribute sets than are read is not judged.

    The part not read might have had the value.
    """
    monkeypatch.setattr(attribute_checking, "MOST_ATTRIBUTE_SETS_PER_ENTITY", 1)
    await _climate(
        hass,
        {"hvac_action": "idle", "current_temperature": 20},
        {"hvac_action": "idle", "current_temperature": 21},
    )
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_set_too_big_to_keep_is_not_whole(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a set the recorder kept empty, as too big, leaves a gap."""
    await _climate(
        hass,
        {"hvac_action": "idle", "current_temperature": 20},
        {"hvac_action": "idle"},
    )

    def _too_big_to_keep() -> None:
        with session_scope(hass=hass) as session:
            session.execute(
                update(StateAttributes)
                .where(StateAttributes.shared_attrs.contains("current_temperature"))
                .values(shared_attrs="{}")
            )

    await get_instance(hass).async_add_executor_job(_too_big_to_keep)
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_recorder_error_means_no_history(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a failing query is no history, not a finding, and not remembered."""
    await _climate(hass, {"hvac_action": "idle"})

    def _fail(*_: object) -> None:
        statement = "SELECT"
        raise OperationalError(statement, {}, Exception("database is locked"))

    monkeypatch.setattr(attribute_value_checking, "_read_recorded_values", _fail)
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None
    assert hass.data[DATA_ATTRIBUTE_VALUE_KNOWLEDGE][CLIMATE].answer is None


@pytest.mark.usefixtures("recorder_mock")
async def test_a_change_while_asking_leaves_the_history_short(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an entity that changed while the recorder was asked is not judged.

    What it passed through may not be written down yet.
    """
    await _climate(hass, {"hvac_action": "idle"})
    asking = attribute_value_checking._async_ask_the_recorder  # noqa: SLF001

    async def _passes_through(hass: HomeAssistant, previous: object) -> None:
        await asking(hass, previous)
        hass.states.async_set(CLIMATE, "heat", {"hvac_action": "idle", "x": 1})

    monkeypatch.setattr(
        attribute_value_checking, "_async_ask_the_recorder", _passes_through
    )
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_stale_history_is_read_again(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an answer too old to go by is not taken for the whole history."""
    await _climate(hass, {"hvac_action": "idle"})
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Heating")])
    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert _found(issue_registry)

    # The day is long gone, and the recorder cannot be read again.
    def _fail(*_: object) -> None:
        statement = "SELECT"
        raise OperationalError(statement, {}, Exception("database is locked"))

    monkeypatch.setattr(attribute_value_checking, "_read_recorded_values", _fail)
    later = dt_util.utcnow() + timedelta(days=2)
    monkeypatch.setattr(attribute_value_checking.dt_util, "utcnow", lambda: later)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_enum_that_cannot_be_found_means_no_set(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an enum that cannot be found is no set, and nothing is judged."""
    monkeypatch.setitem(
        attribute_value_checking._VALUE_ENUMS,  # noqa: SLF001
        ("climate", "hvac_action"),
        "NotAnEnum",
    )
    hass.data.pop(DATA_ATTRIBUTE_VALUES, None)
    await _climate(hass, {"hvac_action": "idle"})
    await _automation(hass, triggers=[_attribute_trigger("hvac_action", to="Idle")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_two_candidates_make_no_suggestion(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a slip of two known values is reported without a guess."""
    await _climate(hass, {"preset_modes": ["eco", "Eco"], "preset_mode": "eco"})
    await _automation(hass, triggers=[_attribute_trigger("preset_mode", to="ECO")])

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) == "- `preset_mode` of `climate.living_room`: `ECO`"


@pytest.mark.usefixtures("recorder_mock")
async def test_value_keeps_its_type_in_the_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a boolean and the same word as text are two findings, not one."""
    await _climate(hass, {"preset_modes": ["true"], "preset_mode": "true"})
    await _automation(
        hass, triggers=[_attribute_trigger("preset_mode", to=[True, "True"])]
    )

    await SpookRepair(hass).async_inspect()

    assert _found(issue_registry) == (
        '- `preset_mode` of `climate.living_room`: `True` (did you mean `"true"`?)\n'
        '- `preset_mode` of `climate.living_room`: `true` (did you mean `"true"`?)'
    )
