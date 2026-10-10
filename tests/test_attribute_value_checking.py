"""Tests for telling a value an attribute can have from one it never has."""

# pylint: disable=protected-access
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from homeassistant.components.climate import ClimateEntity, HVACAction
from homeassistant.components.light import ColorMode
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util

from custom_components.spook import attribute_value_checking
from custom_components.spook.attribute_value_checking import (
    DATA_ATTRIBUTE_VALUE_KNOWLEDGE,
    UnknownAttributeValue,
    async_fixed_values,
    async_unknown_attribute_values,
)
from custom_components.spook.reference_extraction import AttributeValue
from tests.entity_objects import give_entity_objects

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

CLIMATE = "climate.living_room"
HEATING = {(CLIMATE, AttributeValue("hvac_action", "Heating"))}
FOUND = {UnknownAttributeValue(CLIMATE, "hvac_action", "Heating", "heating")}


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


@pytest.fixture(name="count_recorder_reads")
def fixture_count_recorder_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, float | None]]:
    """Note every time the recorder is asked, about which entities, since when."""
    asked: list[dict[str, float | None]] = []
    original = attribute_value_checking._read_recorded_values  # noqa: SLF001

    def _read(
        hass: HomeAssistant, since_by_entity: dict[str, float | None], checked: Any
    ) -> object:
        asked.append(dict(since_by_entity))
        return original(hass, since_by_entity, checked)

    monkeypatch.setattr(attribute_value_checking, "_read_recorded_values", _read)
    return asked


async def _record(hass: HomeAssistant, *hvac_actions: str) -> None:
    """Make the climate entity core's own, give it each action, wait for it."""
    give_entity_objects(hass, CLIMATE, kind=ClimateEntity)
    for hvac_action in hvac_actions:
        hass.states.async_set(CLIMATE, "heat", {"hvac_action": hvac_action})
    await async_wait_recording_done(hass)


async def test_enum_values_are_read_from_core(hass: HomeAssistant) -> None:
    """Test an attribute core has an enum for gets exactly that enum's values."""
    assert await async_fixed_values(hass, "climate", "hvac_action") == frozenset(
        HVACAction
    )
    assert await async_fixed_values(hass, "light", "color_mode") == frozenset(ColorMode)


async def test_fixed_values_without_an_enum(hass: HomeAssistant) -> None:
    """Test an attribute core has no enum for comes from the frontend's list."""
    assert await async_fixed_values(hass, "water_heater", "away_mode") == {
        "on",
        "off",
    }


@pytest.mark.parametrize(
    ("domain", "attribute"),
    [("climate", "fan_mode"), ("climate", "current_temperature"), ("nope", "x")],
)
async def test_free_attributes_have_no_fixed_values(
    hass: HomeAssistant, domain: str, attribute: str
) -> None:
    """Test an attribute with options, or none at all, has no fixed set."""
    assert await async_fixed_values(hass, domain, attribute) is None


async def test_entity_the_recorder_leaves_out_has_no_history(
    recorder_mock: Any,
    hass: HomeAssistant,
) -> None:
    """Test an entity excluded from recording is not judged.

    Not even with an answer from before it was left out: what it had since
    is nowhere.
    """
    await _record(hass, "idle")
    assert await async_unknown_attribute_values(hass, HEATING) == FOUND

    recorder_mock.entity_filter = lambda entity_id: entity_id != CLIMATE

    assert not await async_unknown_attribute_values(hass, HEATING)


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_remembered(
    hass: HomeAssistant, count_recorder_reads: list[dict[str, float | None]]
) -> None:
    """Test all of the history is read once, and after that only what is new."""
    await _record(hass, "idle", "cooling")

    for _ in range(3):
        assert await async_unknown_attribute_values(hass, HEATING) == FOUND

    first, *after = count_recorder_reads
    assert first == {CLIMATE: None}
    assert len(after) == 2  # noqa: PLR2004
    assert all(read[CLIMATE] is not None for read in after)


@pytest.mark.usefixtures("recorder_mock")
async def test_value_that_came_and_went_between_rounds_counts(
    hass: HomeAssistant,
) -> None:
    """Test a value that came and went between two rounds counts.

    Spook did not see it come by, but the recorder did.
    """
    await _record(hass, "idle")
    assert await async_unknown_attribute_values(hass, HEATING) == FOUND

    await _record(hass, "Heating", "idle")

    assert not await async_unknown_attribute_values(hass, HEATING)


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_asked_again_for_a_new_value(
    hass: HomeAssistant, count_recorder_reads: list[dict[str, float | None]]
) -> None:
    """Test an entity with a value Spook did not know is asked about in full."""
    await _record(hass, "idle")
    assert await async_unknown_attribute_values(hass, HEATING)

    await _record(hass, "cooling")
    assert await async_unknown_attribute_values(hass, HEATING)

    assert count_recorder_reads[-1] == {CLIMATE: None}


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_asked_again_after_a_day(
    hass: HomeAssistant,
    count_recorder_reads: list[dict[str, float | None]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test what the recorder said goes stale after a day."""
    await _record(hass, "idle")
    assert await async_unknown_attribute_values(hass, HEATING)

    tomorrow = dt_util.utcnow() + timedelta(days=1, minutes=1)
    monkeypatch.setattr(attribute_value_checking.dt_util, "utcnow", lambda: tomorrow)
    assert await async_unknown_attribute_values(hass, HEATING)

    assert count_recorder_reads == [{CLIMATE: None}, {CLIMATE: None}]


@pytest.mark.usefixtures("recorder_mock")
async def test_answer_dropped_while_reading_news_is_not_continued(
    hass: HomeAssistant,
    count_recorder_reads: list[dict[str, float | None]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test news read for an answer dropped meanwhile does not bring it back."""
    await _record(hass, "idle")
    assert await async_unknown_attribute_values(hass, HEATING)
    asking = attribute_value_checking._async_ask_the_recorder  # noqa: SLF001

    async def _new_value_meanwhile(hass: HomeAssistant, previous: dict) -> None:
        attribute_value_checking._knowledge(hass, CLIMATE).see(  # noqa: SLF001
            {"hvac_action": "drying"}, {"hvac_action"}
        )
        await asking(hass, previous)

    monkeypatch.setattr(
        attribute_value_checking, "_async_ask_the_recorder", _new_value_meanwhile
    )
    await async_unknown_attribute_values(hass, HEATING)
    assert count_recorder_reads[-1][CLIMATE] is not None

    assert hass.data[DATA_ATTRIBUTE_VALUE_KNOWLEDGE][CLIMATE].answer is None


@pytest.mark.usefixtures("recorder_mock")
async def test_read_since_a_moment_is_only_what_came_after(
    hass: HomeAssistant,
) -> None:
    """Test a read since a moment leaves out what came before it."""
    await _record(hass, "Heating")
    later = (dt_util.utcnow() + timedelta(hours=1)).timestamp()

    recorded = await get_instance(hass).async_add_executor_job(
        attribute_value_checking._read_recorded_values,  # noqa: SLF001
        hass,
        {CLIMATE: later},
        {CLIMATE: frozenset({"hvac_action"})},
    )

    assert recorded == {CLIMATE: ({}, True)}


@pytest.mark.usefixtures("recorder_mock")
async def test_read_keeps_what_compares(hass: HomeAssistant) -> None:
    """Test values are read as they compare, and an attribute without one counts."""
    give_entity_objects(hass, CLIMATE, kind=ClimateEntity)
    hass.states.async_set(CLIMATE, "heat", {"hvac_action": "idle", "fan_mode": 2})
    hass.states.async_set(CLIMATE, "heat", {"preset_mode": None, "mood": "calm"})
    await async_wait_recording_done(hass)

    recorded = await get_instance(hass).async_add_executor_job(
        attribute_value_checking._read_recorded_values,  # noqa: SLF001
        hass,
        {CLIMATE: None},
        {CLIMATE: frozenset({"hvac_action", "fan_mode", "preset_mode"})},
    )

    assert recorded == {
        CLIMATE: (
            {"hvac_action": {"idle"}, "fan_mode": {2}, "preset_mode": set()},
            True,
        )
    }
