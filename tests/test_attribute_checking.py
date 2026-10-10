"""Tests for telling an attribute an entity has from one it never had."""

# pylint: disable=protected-access
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)
from sqlalchemy.exc import OperationalError

from homeassistant.core import State
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util

from custom_components.spook import attribute_checking
from custom_components.spook.attribute_checking import (
    DATA_ATTRIBUTE_KNOWLEDGE,
    GENERIC_ATTRIBUTES,
    UnknownAttribute,
    async_domain_attributes,
    async_unknown_attributes,
    suggest_attribute,
)

if TYPE_CHECKING:
    from homeassistant.components.recorder import Recorder
    from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_db_url: str,
    enable_custom_integrations: None,
) -> None:
    """Prepare the recorder's database before Home Assistant starts.

    The recorder fixtures insist on going first, and the shared fixture that
    enables custom integrations starts Home Assistant. Asking for the
    database first puts them in the order they need.
    """
    _ = recorder_db_url, enable_custom_integrations


@pytest.fixture(name="count_recorder_reads")
def fixture_count_recorder_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, float | None]]:
    """Note every time the recorder is asked, about which entities, since when.

    `None` is all of an entity's history, a moment is what came after it.
    """
    asked: list[dict[str, float | None]] = []
    original = attribute_checking._read_recorded_attribute_keys  # noqa: SLF001

    def _read(hass: HomeAssistant, since_by_entity: dict[str, float | None]) -> object:
        asked.append(dict(since_by_entity))
        return original(hass, since_by_entity)

    monkeypatch.setattr(attribute_checking, "_read_recorded_attribute_keys", _read)
    return asked


async def _record(hass: HomeAssistant, entity_id: str, *attribute_sets: dict) -> None:
    """Set an entity to each of these attribute sets, and wait for the recorder."""
    for index, attributes in enumerate(attribute_sets):
        hass.states.async_set(entity_id, str(index), attributes)
    await async_wait_recording_done(hass)


# What is valid, from memory.


async def test_domain_enum_is_read_from_core(hass: HomeAssistant) -> None:
    """Test a domain's attributes come from core's own enums.

    The state ones and the capability ones, and also for a domain that spells
    its enum a little differently, like water heaters.
    """
    light = await async_domain_attributes(hass, "light")
    assert "brightness" in light
    assert "supported_color_modes" in light

    assert "operation_mode" in await async_domain_attributes(hass, "water_heater")
    assert await async_domain_attributes(hass, "sun") == frozenset()
    assert await async_domain_attributes(hass, "not_a_domain") == frozenset()


async def test_domain_enum_is_cached(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a domain is only looked up once."""
    assert "brightness" in await async_domain_attributes(hass, "light")

    def _no_more(*_: object) -> None:
        pytest.fail("looked up a second time")

    monkeypatch.setattr(attribute_checking, "_attributes_from_module", _no_more)
    assert "brightness" in await async_domain_attributes(hass, "light")


def test_generic_attributes_cover_what_every_entity_can_carry() -> None:
    """Test the attributes any entity can have are known everywhere."""
    assert {
        "friendly_name",
        "icon",
        "device_class",
        "unit_of_measurement",
        "supported_features",
        "entity_picture",
        "assumed_state",
        "restored",
        "attribution",
        "editable",
        "id",
        "entity_id",
    } <= GENERIC_ATTRIBUTES


@pytest.mark.usefixtures("recorder_mock")
async def test_known_from_memory_is_not_reported(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the enum, generic and current attributes are all fine.

    With a recorder that remembers nothing at all, so each of them has to
    stand on its own. `brightness` is not on the light right now, because it
    is off, and still something lights have. `custom` is on the sensor right
    now.
    """

    def _remembers_nothing(_hass: HomeAssistant, entity_ids: list[str]) -> dict:
        return {entity_id: (set(), True) for entity_id in entity_ids}

    monkeypatch.setattr(
        attribute_checking, "_read_recorded_attribute_keys", _remembers_nothing
    )
    hass.states.async_set("light.kitchen", "off", {"friendly_name": "Kitchen"})
    hass.states.async_set("sensor.custom", "1", {"custom": True})

    assert not await async_unknown_attributes(
        hass,
        {
            ("light.kitchen", "brightness"),
            ("light.kitchen", "icon"),
            ("sensor.custom", "custom"),
        },
    )


async def test_entity_without_state_is_left_alone(hass: HomeAssistant) -> None:
    """Test an entity that does not exist is another repair's business."""
    assert not await async_unknown_attributes(hass, {("light.gone", "Brightness")})


async def test_without_history_only_case_is_reported(hass: HomeAssistant) -> None:
    """Test without a recorder, only a difference in case is a finding.

    `Brightness` next to a real `brightness` is never meant. `whatever` might
    be an attribute that has not shown up yet, and nothing can say otherwise.
    """
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})

    assert await async_unknown_attributes(
        hass,
        {("light.kitchen", "Brightness"), ("light.kitchen", "whatever")},
    ) == {
        UnknownAttribute("light.kitchen", "Brightness", "brightness"),
    }


async def test_case_is_not_judged_for_what_is_kept_out_by_name(
    hass: HomeAssistant,
) -> None:
    """Test an attribute the entity keeps out of the recorder by name is real.

    Names are case-sensitive: an entity can carry `Temperature` next to
    `temperature`, and naming it to leave out of the recorder says so.
    """
    hass.states.async_set(
        "sensor.both",
        "1",
        {"temperature": 20},
        state_info={"unrecorded_attributes": frozenset({"Temperature"})},
    )

    assert not await async_unknown_attributes(hass, {("sensor.both", "Temperature")})


# What is valid, from the recorder.


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_only_in_history_is_fine(
    hass: HomeAssistant,
) -> None:
    """Test an attribute the entity had before, but not now, is not reported."""
    await _record(
        hass, "sensor.weather_alert", {"alert": "storm"}, {"other": 1}, {"other": 2}
    )

    assert not await async_unknown_attributes(hass, {("sensor.weather_alert", "alert")})


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_never_had_is_reported(
    hass: HomeAssistant,
) -> None:
    """Test an attribute absent from every source is reported, with a guess."""
    await _record(hass, "sensor.weather_alert", {"alert": "storm"}, {"other": 1})

    assert await async_unknown_attributes(
        hass,
        {("sensor.weather_alert", "alerts"), ("sensor.weather_alert", "nothing")},
    ) == {
        UnknownAttribute("sensor.weather_alert", "alerts", "alert"),
        UnknownAttribute("sensor.weather_alert", "nothing", None),
    }


@pytest.mark.usefixtures("recorder_mock")
async def test_unrecorded_attribute_is_not_judged_by_history(
    hass: HomeAssistant,
) -> None:
    """Test an attribute the recorder leaves out cannot be missing from it."""
    hass.states.async_set(
        "sensor.quiet",
        "1",
        {},
        state_info={"unrecorded_attributes": frozenset({"secret"})},
    )
    await async_wait_recording_done(hass)

    assert not await async_unknown_attributes(hass, {("sensor.quiet", "secret")})


async def test_entity_the_recorder_leaves_out_has_no_history(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Test an entity excluded from recording is only checked for case."""
    await _record(hass, "sensor.excluded", {"value": 1})
    recorder_mock.entity_filter = lambda entity_id: entity_id != "sensor.excluded"

    assert await async_unknown_attributes(
        hass, {("sensor.excluded", "nothing"), ("sensor.excluded", "Value")}
    ) == {UnknownAttribute("sensor.excluded", "Value", "value")}


@pytest.mark.usefixtures("recorder_mock")
async def test_too_much_history_is_not_judged(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an entity with more history than is read is only checked for case.

    The part not read might have had the attribute.
    """
    monkeypatch.setattr(attribute_checking, "MOST_ATTRIBUTE_SETS_PER_ENTITY", 2)
    await _record(hass, "sensor.chatty", {"old": 1}, {"new": 2}, {"new": 3})

    assert not await async_unknown_attributes(hass, {("sensor.chatty", "old")})
    assert not await async_unknown_attributes(hass, {("sensor.chatty", "nothing")})


@pytest.mark.usefixtures("recorder_mock")
async def test_recorder_error_means_no_history(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a failing query is no history, not a finding, and not remembered."""
    await _record(hass, "sensor.broken", {"value": 1})

    def _fail(*_: object) -> None:
        statement = "SELECT"
        raise OperationalError(statement, {}, Exception("database is locked"))

    monkeypatch.setattr(attribute_checking, "_read_recorded_attribute_keys", _fail)

    assert not await async_unknown_attributes(hass, {("sensor.broken", "nothing")})
    assert hass.data[DATA_ATTRIBUTE_KNOWLEDGE]["sensor.broken"].answer is None


@pytest.mark.usefixtures("recorder_mock")
async def test_damaged_attribute_set_means_no_history(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an attribute set that does not parse is no history, not a crash."""
    await _record(hass, "sensor.damaged", {"value": 1})

    def _damaged(_shared_attrs: str) -> None:
        message = "not JSON"
        raise ValueError(message)

    monkeypatch.setattr(attribute_checking, "json_loads_object", _damaged)

    assert not await async_unknown_attributes(hass, {("sensor.damaged", "nothing")})
    assert hass.data[DATA_ATTRIBUTE_KNOWLEDGE]["sensor.damaged"].answer is None


@pytest.mark.usefixtures("recorder_mock")
async def test_recorder_is_asked_once_for_everything(
    hass: HomeAssistant,
    count_recorder_reads: list[dict[str, float | None]],
) -> None:
    """Test one round asks the recorder once, and only about the leftovers."""
    await _record(hass, "sensor.one", {"a": 1})
    await _record(hass, "sensor.two", {"b": 1})
    hass.states.async_set("light.kitchen", "on", {"brightness": 1})

    await async_unknown_attributes(
        hass,
        {
            ("sensor.one", "x"),
            ("sensor.two", "y"),
            ("sensor.two", "b"),
            ("light.kitchen", "brightness"),
        },
    )

    assert count_recorder_reads == [{"sensor.one": None, "sensor.two": None}]


@pytest.mark.usefixtures("recorder_mock")
async def test_recorder_is_not_asked_what_it_never_kept(
    hass: HomeAssistant,
    count_recorder_reads: list[dict[str, float | None]],
) -> None:
    """Test the recorder is left alone about attributes it leaves out."""
    hass.states.async_set(
        "sensor.quiet",
        "1",
        {},
        state_info={"unrecorded_attributes": frozenset({"secret"})},
    )
    await async_wait_recording_done(hass)

    await async_unknown_attributes(hass, {("sensor.quiet", "secret")})

    assert not count_recorder_reads


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_remembered(
    hass: HomeAssistant,
    count_recorder_reads: list[dict[str, float | None]],
) -> None:
    """Test all of the history is read once, and after that only what is new.

    What was known is never asked about at all.
    """
    await _record(hass, "sensor.one", {"gone": 1}, {"a": 1})

    for _ in range(3):
        assert await async_unknown_attributes(hass, {("sensor.one", "x")})
        assert not await async_unknown_attributes(hass, {("sensor.one", "gone")})

    first, *after = count_recorder_reads
    assert first == {"sensor.one": None}
    assert len(after) == 2  # noqa: PLR2004
    assert all(read["sensor.one"] is not None for read in after)


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_that_came_and_went_between_rounds_counts(
    hass: HomeAssistant,
) -> None:
    """Test an attribute that showed up and left again between two rounds counts.

    Spook did not see it come by, but the recorder did, and reading what it
    wrote since the last round finds it.
    """
    await _record(hass, "sensor.one", {"a": 1})
    assert await async_unknown_attributes(hass, {("sensor.one", "x")})

    await _record(hass, "sensor.one", {"a": 1, "x": 1}, {"a": 1})

    assert not await async_unknown_attributes(hass, {("sensor.one", "x")})


@pytest.mark.usefixtures("recorder_mock")
async def test_attributes_too_big_to_keep_mean_no_whole_history(
    hass: HomeAssistant,
) -> None:
    """Test a state whose attributes the recorder did not keep leaves a gap.

    Too big, and the recorder keeps an empty set instead. Whatever was in
    there is not in the history, so absence from it means nothing.
    """
    await _record(hass, "sensor.huge", {"a": 1, "x": "spooky" * 4000}, {"a": 1})

    assert not await async_unknown_attributes(hass, {("sensor.huge", "x")})
    assert not await async_unknown_attributes(hass, {("sensor.huge", "nothing")})


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_asked_again_for_a_new_key(
    hass: HomeAssistant,
    count_recorder_reads: list[dict[str, float | None]],
) -> None:
    """Test an entity showing a key it did not have is worth asking about again."""
    await _record(hass, "sensor.one", {"a": 1})
    assert await async_unknown_attributes(hass, {("sensor.one", "x")})

    # Same keys, new values: only what is new is read.
    await _record(hass, "sensor.one", {"a": 2})
    assert await async_unknown_attributes(hass, {("sensor.one", "x")})
    assert count_recorder_reads[-1]["sensor.one"] is not None

    await _record(hass, "sensor.one", {"a": 2, "b": 1})
    assert await async_unknown_attributes(hass, {("sensor.one", "x")})
    assert count_recorder_reads[-1] == {"sensor.one": None}


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_asked_again_after_a_day(
    hass: HomeAssistant,
    count_recorder_reads: list[dict[str, float | None]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test what the recorder said goes stale after a day."""
    await _record(hass, "sensor.one", {"a": 1})
    assert await async_unknown_attributes(hass, {("sensor.one", "x")})

    tomorrow = dt_util.utcnow() + timedelta(days=1, minutes=1)
    monkeypatch.setattr(attribute_checking.dt_util, "utcnow", lambda: tomorrow)
    assert await async_unknown_attributes(hass, {("sensor.one", "x")})

    assert count_recorder_reads == [{"sensor.one": None}, {"sensor.one": None}]


@pytest.mark.usefixtures("recorder_mock")
async def test_what_was_seen_is_kept_after_a_purge(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a key the recorder once showed stays known, even once purged."""
    await _record(hass, "sensor.one", {"old": 1}, {"a": 1})
    assert not await async_unknown_attributes(hass, {("sensor.one", "old")})

    def _purged(_hass: HomeAssistant, entity_ids: list[str]) -> dict:
        return {entity_id: ({"a"}, True) for entity_id in entity_ids}

    monkeypatch.setattr(attribute_checking, "_read_recorded_attribute_keys", _purged)
    tomorrow = dt_util.utcnow() + timedelta(days=2)
    monkeypatch.setattr(attribute_checking.dt_util, "utcnow", lambda: tomorrow)

    assert not await async_unknown_attributes(hass, {("sensor.one", "old")})


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_bounded_in_the_database(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test only the newest states are read, and more than that is not whole.

    `old` is only in a state older than the bound, so it is never read, and
    the answer says it is not the whole history.
    """
    monkeypatch.setattr(attribute_checking, "MOST_STATES_PER_ENTITY", 2)
    await _record(hass, "sensor.long", {"old": 1}, {"a": 1}, {"a": 2}, {"a": 3})

    recorded = await get_instance(hass).async_add_executor_job(
        attribute_checking._read_recorded_attribute_keys,  # noqa: SLF001
        hass,
        {"sensor.long": None, "sensor.never_recorded": None},
    )

    assert recorded == {"sensor.long": ({"a"}, False)}


@pytest.fixture(name="recorder_remembers_only_a")
def fixture_recorder_remembers_only_a(
    monkeypatch: pytest.MonkeyPatch,
) -> list[list[str]]:
    """Stand in for the recorder, remembering the whole history and only `a`."""
    asked: list[list[str]] = []

    def _only_a(_hass: HomeAssistant, entity_ids: list[str]) -> dict:
        asked.append(list(entity_ids))
        return {entity_id: ({"a"}, True) for entity_id in entity_ids}

    monkeypatch.setattr(attribute_checking, "_read_recorded_attribute_keys", _only_a)
    return asked


@pytest.mark.usefixtures("recorder_mock")
async def test_seen_once_is_known_for_good(
    hass: HomeAssistant,
    recorder_remembers_only_a: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an attribute seen on the entity once is never reported again.

    Not when it is gone again, and not once what the recorder said has gone
    stale either: what was seen is never asked about again.
    """
    hass.states.async_set("sensor.one", "1", {"a": 1})
    assert await async_unknown_attributes(hass, {("sensor.one", "x")})

    hass.states.async_set("sensor.one", "1", {"a": 1, "x": 1})
    assert not await async_unknown_attributes(hass, {("sensor.one", "x")})

    hass.states.async_set("sensor.one", "1", {"a": 1})
    assert not await async_unknown_attributes(hass, {("sensor.one", "x")})

    later = dt_util.utcnow() + timedelta(days=2)
    monkeypatch.setattr(attribute_checking.dt_util, "utcnow", lambda: later)
    assert not await async_unknown_attributes(hass, {("sensor.one", "x")})

    assert len(recorder_remembers_only_a) == 1


@pytest.mark.usefixtures("recorder_mock")
async def test_a_change_while_asking_counts(
    hass: HomeAssistant,
    recorder_remembers_only_a: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the entity is looked at again after the recorder answered.

    It gained `x` while the recorder was being asked, so `x` is not unknown.
    """
    hass.states.async_set("sensor.one", "1", {"a": 1})
    asking = attribute_checking._async_ask_the_recorder  # noqa: SLF001

    async def _changes_while_asking(hass: HomeAssistant, entity_ids: list[str]) -> None:
        await asking(hass, entity_ids)
        hass.states.async_set("sensor.one", "1", {"a": 1, "x": 1})

    monkeypatch.setattr(
        attribute_checking, "_async_ask_the_recorder", _changes_while_asking
    )

    assert not await async_unknown_attributes(hass, {("sensor.one", "x")})
    assert recorder_remembers_only_a


# Did you mean.


@pytest.mark.parametrize(
    ("name", "known", "expected"),
    [
        # Case and separators.
        ("Brightness", {"brightness", "color_temp"}, "brightness"),
        # Each of these is more than one edit away, so only folding finds it.
        ("color temp kelvin", {"color_temp", "color_temp_kelvin"}, "color_temp_kelvin"),
        ("colorTempKelvin", {"color_temp", "color_temp_kelvin"}, "color_temp_kelvin"),
        ("Color-Temp-Kelvin", {"color_temp", "color_temp_kelvin"}, "color_temp_kelvin"),
        # One edit, each kind.
        ("brighness", {"brightness"}, "brightness"),
        ("brightnesss", {"brightness"}, "brightness"),
        ("brigthness", {"brightness"}, "brightness"),
        ("brightnoss", {"brightness"}, "brightness"),
    ],
)
def test_suggestion(name: str, known: set[str], expected: str) -> None:
    """Test a suggestion is made when it is near certain."""
    assert suggest_attribute(name, known) == expected


@pytest.mark.parametrize(
    ("name", "known"),
    [
        # Too short to call a one letter difference a slip.
        ("mode", {"node"}),
        # Two edits away, the kind of near miss a percentage would happily
        # call 80% alike.
        ("brghtnss", {"brightness"}),
        ("temprature", {"temperature_unit"}),
        # More than one candidate qualifies.
        ("color_tamp", {"color_temp", "color_ramp"}),
        ("Color Temp", {"color_temp", "colortemp"}),
        # Nothing alike at all.
        ("whatever", {"brightness"}),
    ],
)
def test_no_suggestion(name: str, known: set[str]) -> None:
    """Test no suggestion is made when it would be a guess."""
    assert suggest_attribute(name, known) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_state_with_unrecorded_wildcard(
    hass: HomeAssistant,
) -> None:
    """Test an entity keeping all its attributes out of the recorder is not judged."""
    hass.states.async_set(
        "sensor.private",
        "1",
        {"value": 1},
        state_info={"unrecorded_attributes": frozenset({"*"})},
    )
    await async_wait_recording_done(hass)

    assert not await async_unknown_attributes(hass, {("sensor.private", "nothing")})
    assert isinstance(hass.states.get("sensor.private"), State)
