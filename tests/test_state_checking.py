"""Tests for telling a state an entity can be in from one it never is."""

# pylint: disable=protected-access
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)
from sqlalchemy import update
from sqlalchemy.exc import OperationalError

from homeassistant.components.climate import ClimateEntity, HVACMode
from homeassistant.components.cover import CoverEntity, CoverState
from homeassistant.components.light import LightEntity
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.recorder.db_schema import States
from homeassistant.helpers.recorder import get_instance, session_scope
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook import state_checking
from custom_components.spook.state_checking import (
    DATA_STATE_KNOWLEDGE,
    UnknownState,
    async_domain_states,
    async_unknown_states,
)
from tests.entity_objects import give_entity_objects


class _CoreSwitch(SwitchEntity):
    """A switch like any integration's, using core's own `state`."""


# Core's own entity classes, for entities that are what they say they are.
_CORE_KINDS = {
    "climate": ClimateEntity,
    "cover": CoverEntity,
    "light": LightEntity,
    "media_player": MediaPlayerEntity,
    "select": SelectEntity,
    "sensor": SensorEntity,
}

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
    enables custom integrations starts Home Assistant.
    """
    _ = recorder_db_url, enable_custom_integrations


@pytest.fixture(name="count_recorder_reads")
def fixture_count_recorder_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, float | None]]:
    """Note every time the recorder is asked, about which entities, since when."""
    asked: list[dict[str, float | None]] = []
    original = state_checking._read_recorded_states  # noqa: SLF001

    def _read(hass: HomeAssistant, since_by_entity: dict[str, float | None]) -> object:
        asked.append(dict(since_by_entity))
        return original(hass, since_by_entity)

    monkeypatch.setattr(state_checking, "_read_recorded_states", _read)
    return asked


def _own(hass: HomeAssistant, *entity_ids: str) -> None:
    """Make these entities their domain's, each of core's own class for it."""
    for entity_id in entity_ids:
        kind = _CORE_KINDS.get(entity_id.split(".", maxsplit=1)[0])
        give_entity_objects(hass, entity_id, kind=kind)


async def _record(
    hass: HomeAssistant, entity_id: str, *states: str, **attributes: object
) -> None:
    """Make an entity its domain's, set it to each state, wait for the recorder."""
    _own(hass, entity_id)
    for state in states:
        hass.states.async_set(entity_id, state, attributes)
    await async_wait_recording_done(hass)


# What is fixed for a domain.


async def test_enum_states_are_read_from_core(hass: HomeAssistant) -> None:
    """Test a domain core has an enum for gets exactly that enum's states."""
    assert await async_domain_states(hass, "cover") == frozenset(CoverState)
    assert await async_domain_states(hass, "climate") == frozenset(HVACMode)


async def test_fixed_states_of_domains_without_an_enum(hass: HomeAssistant) -> None:
    """Test the domains core has no enum for come from the frontend's list."""
    assert await async_domain_states(hass, "light") == {"on", "off"}
    assert await async_domain_states(hass, "sun") == {
        "above_horizon",
        "below_horizon",
    }


@pytest.mark.parametrize(
    "domain",
    ["sensor", "number", "text", "counter", "person", "device_tracker", "nope"],
)
async def test_free_domains_have_no_fixed_states(
    hass: HomeAssistant, domain: str
) -> None:
    """Test a domain whose states can be anything, or zone names, has no set."""
    assert await async_domain_states(hass, domain) is None


async def test_enum_that_does_not_import_means_no_set(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test an enum that cannot be found is no set, not the frontend's list."""
    monkeypatch.setitem(
        state_checking._STATE_ENUMS,  # noqa: SLF001
        "cover",
        ("not_a_module", "CoverState"),
    )

    assert await async_domain_states(hass, "cover") is None


async def test_domain_states_are_cached(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a domain is only looked up once."""
    assert await async_domain_states(hass, "cover")

    def _no_more(*_: object) -> None:
        pytest.fail("looked up a second time")

    monkeypatch.setattr(state_checking, "_states_from_module", _no_more)
    assert await async_domain_states(hass, "cover")


# Which entities are checked at all.


async def test_case_only_is_reported_without_history(hass: HomeAssistant) -> None:
    """Test `On` for a light is reported, recorder or not, with a guess."""
    _own(hass, "light.kitchen")
    hass.states.async_set("light.kitchen", "off")

    assert await async_unknown_states(
        hass, {("light.kitchen", "On"), ("light.kitchen", "dimmed")}
    ) == {UnknownState("light.kitchen", "On", "on")}


async def test_entity_without_an_entity_object_is_left_alone(
    hass: HomeAssistant,
) -> None:
    """Test a state set from outside, by a REST call say, is never judged."""
    hass.states.async_set("light.from_rest", "off")

    assert not await async_unknown_states(hass, {("light.from_rest", "On")})


async def test_entity_without_state_is_left_alone(hass: HomeAssistant) -> None:
    """Test an entity that does not exist is another repair's business."""
    _own(hass, "light.gone")

    assert not await async_unknown_states(hass, {("light.gone", "On")})


async def test_free_domain_is_left_alone(hass: HomeAssistant) -> None:
    """Test a plain sensor can be anything, also something only in case apart."""
    _own(hass, "sensor.mode")
    hass.states.async_set("sensor.mode", "on")

    assert not await async_unknown_states(hass, {("sensor.mode", "On")})


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize("state", ["unavailable", "unknown"])
async def test_unavailable_and_unknown_are_always_fine(
    hass: HomeAssistant, state: str
) -> None:
    """Test the states any entity can be in are never reported.

    Not even with a whole history that never had them.
    """
    await _record(hass, "light.kitchen", "on")

    assert not await async_unknown_states(hass, {("light.kitchen", state)})


async def test_domain_whose_enum_did_not_come_is_left_alone(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a climate entity is not checked on its modes alone.

    Without the enum, the modes it offers are all there is to go by, and
    they never were all a climate entity can be in.
    """
    monkeypatch.setitem(
        state_checking._STATE_ENUMS,  # noqa: SLF001
        "climate",
        ("not_a_module", "HVACMode"),
    )
    _own(hass, "climate.hall")
    hass.states.async_set("climate.hall", "heat", {"hvac_modes": ["heat", "off"]})

    assert not await async_unknown_states(hass, {("climate.hall", "Heat")})


# Options.


@pytest.mark.usefixtures("recorder_mock")
async def test_options_of_a_select(hass: HomeAssistant) -> None:
    """Test a select's options are what it can be, and case counts.

    Only a case slip, with the whole history: a select gets new options at
    any moment, so what is not one today can be tomorrow.
    """
    await _record(hass, "select.mode", "eco", options=["eco", "boost"])

    assert await async_unknown_states(
        hass,
        {("select.mode", "boost"), ("select.mode", "Boost"), ("select.mode", "away")},
    ) == {UnknownState("select.mode", "Boost", "boost")}


async def test_select_case_slip_needs_history(hass: HomeAssistant) -> None:
    """Test a select's case slip is not reported without history."""
    _own(hass, "select.mode")
    hass.states.async_set("select.mode", "eco", {"options": ["eco", "boost"]})

    assert not await async_unknown_states(hass, {("select.mode", "Boost")})


async def test_select_state_between_looks_is_not_reported(
    hass: HomeAssistant,
) -> None:
    """Test a select that was in a state between two looks is not judged on it.

    Without a recorder there is no knowing what it was in meanwhile: `eco`,
    then `Boost` after its options changed, then `eco` again. `Boost` looks
    like a case slip of `boost`, and still was real.
    """
    _own(hass, "select.mode")
    hass.states.async_set("select.mode", "eco", {"options": ["eco", "boost"]})
    assert not await async_unknown_states(hass, {("select.mode", "eco")})

    hass.states.async_set("select.mode", "Boost", {"options": ["eco", "Boost"]})
    hass.states.async_set("select.mode", "eco", {"options": ["eco", "boost"]})

    assert not await async_unknown_states(hass, {("select.mode", "Boost")})


async def _dropdown(hass: HomeAssistant) -> None:
    """Set up a real dropdown helper, held by its own component."""
    assert await async_setup_component(
        hass,
        "input_select",
        {"input_select": {"mode": {"options": ["Eco", "Boost"]}}},
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("recorder_mock")
async def test_dropdown_options_can_change_while_running(hass: HomeAssistant) -> None:
    """Test a dropdown helper is never held to the options it has right now.

    A script can set its options and then wait for one of the new ones, so
    only a case slip is reported, and only with the whole history.
    """
    await _dropdown(hass)
    await async_wait_recording_done(hass)

    assert not await async_unknown_states(hass, {("input_select.mode", "Holiday")})
    assert await async_unknown_states(hass, {("input_select.mode", "boost")}) == {
        UnknownState("input_select.mode", "boost", "Boost")
    }


async def test_dropdown_case_slip_needs_history(hass: HomeAssistant) -> None:
    """Test a dropdown helper's case slip is not reported without history."""
    await _dropdown(hass)

    assert not await async_unknown_states(hass, {("input_select.mode", "boost")})


@pytest.mark.usefixtures("recorder_mock")
async def test_options_that_changed_are_still_fine(hass: HomeAssistant) -> None:
    """Test an option the entity offered once stays known.

    Options come and go, like a source list, and one gone now may be back.
    """
    await _record(hass, "select.mode", "eco", options=["eco", "Boost"])
    assert not await async_unknown_states(hass, {("select.mode", "Boost")})

    hass.states.async_set("select.mode", "eco", {"options": ["eco", "away"]})
    await async_wait_recording_done(hass)

    assert not await async_unknown_states(hass, {("select.mode", "Boost")})
    assert await async_unknown_states(hass, {("select.mode", "boost")}) == {
        UnknownState("select.mode", "boost", "Boost")
    }


@pytest.mark.usefixtures("recorder_mock")
async def test_enum_sensor_is_checked_on_its_options(hass: HomeAssistant) -> None:
    """Test a sensor with fixed values is checked, and only as an enum."""
    await _record(
        hass, "sensor.washer", "idle", device_class="enum", options=["idle", "washing"]
    )
    await _record(hass, "sensor.not_enum", "idle", options=["idle"])

    assert await async_unknown_states(
        hass,
        {
            ("sensor.washer", "Washing"),
            ("sensor.washer", "drying"),
            ("sensor.not_enum", "Idle"),
        },
    ) == {UnknownState("sensor.washer", "Washing", "washing")}


async def test_climate_can_be_in_any_mode_of_its_enum(hass: HomeAssistant) -> None:
    """Test a climate entity is checked against the enum, not its modes alone."""
    _own(hass, "climate.hall")
    hass.states.async_set("climate.hall", "heat", {"hvac_modes": ["heat", "off"]})

    assert not await async_unknown_states(hass, {("climate.hall", "heat_cool")})
    assert await async_unknown_states(hass, {("climate.hall", "Heat")}) == {
        UnknownState("climate.hall", "Heat", "heat")
    }


@pytest.mark.usefixtures("recorder_mock")
async def test_water_heater_is_left_alone(hass: HomeAssistant) -> None:
    """Test a water heater is not checked against its operation list.

    Its state is the current operation, which core does not hold to the
    list: some integrations report `off` without offering it.
    """
    await _record(hass, "water_heater.boiler", "eco", operation_list=["eco"])

    assert not await async_unknown_states(hass, {("water_heater.boiler", "off")})


# Where core keeps the set, and where it does not.


class _LightOfItsOwn(LightEntity):
    """A light that works out its state itself, instead of from `is_on`.

    Core says not to, and an integration can still do it: that is the case.
    """

    @property
    # pylint: disable-next=overridden-final-method
    def state(self) -> str:  # type: ignore[override]
        """Return whatever it likes."""
        return "dimmed"


def test_core_light_keeps_the_set() -> None:
    """Test core's own light, and a subclass using its `state`, keep the set."""
    assert state_checking._set_is_kept("light", LightEntity())  # noqa: SLF001
    assert state_checking._set_is_kept("switch", _CoreSwitch())  # noqa: SLF001


@pytest.mark.parametrize(
    ("domain", "entity"),
    [
        pytest.param("light", _LightOfItsOwn(), id="a state of its own"),
        pytest.param("light", object(), id="not an entity of the domain"),
        pytest.param("media_player", MediaPlayerEntity(), id="media player"),
        pytest.param("input_select", SelectEntity(), id="dropdown helper"),
        pytest.param("select", SelectEntity(), id="select"),
        pytest.param("sensor", SensorEntity(), id="sensor"),
        pytest.param("light", SensorEntity(), id="another domain's class"),
    ],
)
def test_set_is_not_kept(domain: str, entity: object) -> None:
    """Test an entity core does not hold to the set is never taken as held."""
    assert not state_checking._set_is_kept(domain, entity)  # noqa: SLF001


async def test_light_of_its_own_needs_history_even_for_case(
    hass: HomeAssistant,
) -> None:
    """Test a light with a state of its own is not judged without history.

    Not even `On`: it can be in anything, and with no recorder there is no
    knowing it never was, between two looks.
    """
    give_entity_objects(hass, "light.own", kind=_LightOfItsOwn)
    hass.states.async_set("light.own", "off")

    assert not await async_unknown_states(hass, {("light.own", "On")})


@pytest.mark.usefixtures("recorder_mock")
async def test_light_of_its_own_gets_only_case_slips(hass: HomeAssistant) -> None:
    """Test a light with a state of its own gets only a case slip, from history."""
    give_entity_objects(hass, "light.own", kind=_LightOfItsOwn)
    hass.states.async_set("light.own", "on")
    hass.states.async_set("light.own", "off")
    await async_wait_recording_done(hass)

    assert await async_unknown_states(
        hass, {("light.own", "On"), ("light.own", "glowing")}
    ) == {UnknownState("light.own", "On", "on")}


@pytest.mark.usefixtures("recorder_mock")
async def test_media_player_can_be_in_anything(hass: HomeAssistant) -> None:
    """Test a media player is never told a state is impossible.

    Core does not hold it to its enum: one made from a template is in
    whatever the template says. A whole history of `off` proves nothing
    about `zapping`. A case slip it still gets.
    """
    await _record(hass, "media_player.tv", "off")

    assert await async_unknown_states(
        hass, {("media_player.tv", "zapping"), ("media_player.tv", "Off")}
    ) == {UnknownState("media_player.tv", "Off", "off")}


async def test_media_player_case_slip_needs_history(hass: HomeAssistant) -> None:
    """Test a media player's case slip is not reported without history."""
    _own(hass, "media_player.tv")
    hass.states.async_set("media_player.tv", "off")

    assert not await async_unknown_states(hass, {("media_player.tv", "Off")})


@pytest.mark.usefixtures("recorder_mock")
async def test_what_a_sensor_was_does_not_make_it_checked(hass: HomeAssistant) -> None:
    """Test a sensor that was an enum once is not checked as one now.

    Replaced by a plain sensor under the same entity ID, it can be anything.
    """
    await _record(
        hass, "sensor.washer", "idle", device_class="enum", options=["washing"]
    )
    assert await async_unknown_states(hass, {("sensor.washer", "Washing")})

    hass.states.async_set("sensor.washer", "idle")
    await async_wait_recording_done(hass)

    assert not await async_unknown_states(hass, {("sensor.washer", "Washing")})


# History.


@pytest.mark.usefixtures("recorder_mock")
async def test_state_never_had_is_reported(hass: HomeAssistant) -> None:
    """Test a state outside of everything is reported, with the whole history."""
    await _record(hass, "light.kitchen", "on", "off")

    assert await async_unknown_states(
        hass, {("light.kitchen", "dimmed"), ("light.kitchen", "on")}
    ) == {UnknownState("light.kitchen", "dimmed", None)}


async def test_without_a_recorder_only_case_is_reported(hass: HomeAssistant) -> None:
    """Test without history, a state not in the set might still come by."""
    _own(hass, "light.tv")
    hass.states.async_set("light.tv", "on")

    assert not await async_unknown_states(hass, {("light.tv", "dimmed")})


@pytest.mark.usefixtures("recorder_mock")
async def test_state_only_in_history_is_fine(hass: HomeAssistant) -> None:
    """Test a state the entity was once in counts, outside of its set or not.

    An integration that does its own thing shows up in history.
    """
    await _record(hass, "light.tv", "dimmed", "on")

    assert not await async_unknown_states(hass, {("light.tv", "dimmed")})


async def test_entity_the_recorder_leaves_out_has_no_history(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Test an entity excluded from recording is only checked for case."""
    await _record(hass, "light.excluded", "on")
    recorder_mock.entity_filter = lambda entity_id: entity_id != "light.excluded"

    assert await async_unknown_states(
        hass, {("light.excluded", "dimmed"), ("light.excluded", "ON")}
    ) == {UnknownState("light.excluded", "ON", "on")}


@pytest.mark.usefixtures("recorder_mock")
async def test_too_much_history_is_not_judged(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test an entity with more history than is read is only checked for case."""
    monkeypatch.setattr(state_checking, "MOST_STATES_PER_ENTITY", 2)
    await _record(hass, "light.tv", "dimmed", "on", "off", "on")

    assert not await async_unknown_states(hass, {("light.tv", "dimmed")})
    assert not await async_unknown_states(hass, {("light.tv", "nothing")})


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_bounded_in_the_database(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test only the newest states are read, and more than that is not whole."""
    monkeypatch.setattr(state_checking, "MOST_STATES_PER_ENTITY", 2)
    await _record(hass, "light.tv", "dimmed", "on", "off", "on")

    recorded = await get_instance(hass).async_add_executor_job(
        state_checking._read_recorded_states,  # noqa: SLF001
        hass,
        {"light.tv": None, "media_player.never_recorded": None},
    )

    assert recorded == {"light.tv": ({"on", "off"}, False)}


@pytest.mark.usefixtures("recorder_mock")
async def test_recorder_error_means_no_history(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a failing query is no history, not a finding, and not remembered."""
    await _record(hass, "light.kitchen", "on")

    def _fail(*_: object) -> None:
        statement = "SELECT"
        raise OperationalError(statement, {}, Exception("database is locked"))

    monkeypatch.setattr(state_checking, "_read_recorded_states", _fail)

    assert not await async_unknown_states(hass, {("light.kitchen", "dimmed")})
    assert hass.data[DATA_STATE_KNOWLEDGE]["light.kitchen"].answer is None


@pytest.mark.usefixtures("recorder_mock")
async def test_recorder_is_asked_once_for_everything(
    hass: HomeAssistant, count_recorder_reads: list[dict[str, float | None]]
) -> None:
    """Test one round asks the recorder once, and only about the leftovers."""
    await _record(hass, "light.one", "on")
    await _record(hass, "light.two", "off")
    await _record(hass, "light.three", "off")

    await async_unknown_states(
        hass,
        {("light.one", "dimmed"), ("light.two", "dimmed"), ("light.three", "on")},
    )

    assert count_recorder_reads == [{"light.one": None, "light.two": None}]


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_remembered(
    hass: HomeAssistant, count_recorder_reads: list[dict[str, float | None]]
) -> None:
    """Test all of the history is read once, and after that only what is new."""
    await _record(hass, "light.one", "on", "off")

    for _ in range(3):
        assert await async_unknown_states(hass, {("light.one", "dimmed")})

    first, *after = count_recorder_reads
    assert first == {"light.one": None}
    assert len(after) == 2  # noqa: PLR2004
    assert all(read["light.one"] is not None for read in after)


@pytest.mark.usefixtures("recorder_mock")
async def test_state_that_came_and_went_between_rounds_counts(
    hass: HomeAssistant,
) -> None:
    """Test a state that came and went between two rounds counts.

    Spook did not see it come by, but the recorder did.
    """
    await _record(hass, "light.tv", "on")
    assert await async_unknown_states(hass, {("light.tv", "dimmed")})

    await _record(hass, "light.tv", "dimmed", "on")

    assert not await async_unknown_states(hass, {("light.tv", "dimmed")})


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_asked_again_for_a_new_state(
    hass: HomeAssistant, count_recorder_reads: list[dict[str, float | None]]
) -> None:
    """Test an entity in a state Spook did not know is asked about in full."""
    await _record(hass, "light.tv", "on")
    assert await async_unknown_states(hass, {("light.tv", "dimmed")})

    await _record(hass, "light.tv", "on")
    assert await async_unknown_states(hass, {("light.tv", "dimmed")})
    assert count_recorder_reads[-1]["light.tv"] is not None

    await _record(hass, "light.tv", "off")
    assert await async_unknown_states(hass, {("light.tv", "dimmed")})
    assert count_recorder_reads[-1] == {"light.tv": None}


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_asked_again_after_a_day(
    hass: HomeAssistant,
    count_recorder_reads: list[dict[str, float | None]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test what the recorder said goes stale after a day."""
    await _record(hass, "light.one", "on")
    assert await async_unknown_states(hass, {("light.one", "dimmed")})

    tomorrow = dt_util.utcnow() + timedelta(days=1, minutes=1)
    monkeypatch.setattr(state_checking.dt_util, "utcnow", lambda: tomorrow)
    assert await async_unknown_states(hass, {("light.one", "dimmed")})

    assert count_recorder_reads == [{"light.one": None}, {"light.one": None}]


@pytest.mark.usefixtures("recorder_mock")
async def test_a_change_while_asking_counts(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the entity is looked at again after the recorder answered.

    It went to `zapping` while the recorder was being asked, so that is fine.
    """
    await _record(hass, "light.tv", "on")
    asking = state_checking._async_ask_the_recorder  # noqa: SLF001

    async def _changes_while_asking(hass: HomeAssistant, entity_ids: object) -> None:
        await asking(hass, entity_ids)
        hass.states.async_set("light.tv", "dimmed")

    monkeypatch.setattr(
        state_checking, "_async_ask_the_recorder", _changes_while_asking
    )

    assert not await async_unknown_states(hass, {("light.tv", "dimmed")})


@pytest.mark.usefixtures("recorder_mock")
async def test_seen_once_is_known_for_good(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a state seen on the entity once is never reported again.

    Not once it is purged from history, and not once the answer is stale.
    """
    _own(hass, "light.tv")
    hass.states.async_set("light.tv", "dimmed")
    assert not await async_unknown_states(hass, {("light.tv", "dimmed")})
    hass.states.async_set("light.tv", "on")

    def _purged(_hass: HomeAssistant, entity_ids: list[str]) -> dict:
        return {entity_id: ({"on"}, True) for entity_id in entity_ids}

    monkeypatch.setattr(state_checking, "_read_recorded_states", _purged)
    later = dt_util.utcnow() + timedelta(days=2)
    monkeypatch.setattr(state_checking.dt_util, "utcnow", lambda: later)

    assert not await async_unknown_states(hass, {("light.tv", "dimmed")})


@pytest.mark.usefixtures("recorder_mock")
async def test_read_since_a_moment_is_only_what_came_after(
    hass: HomeAssistant,
) -> None:
    """Test a read since a moment leaves out what came before it."""
    await _record(hass, "light.tv", "dimmed")
    later = (dt_util.utcnow() + timedelta(hours=1)).timestamp()

    recorded = await get_instance(hass).async_add_executor_job(
        state_checking._read_recorded_states,  # noqa: SLF001
        hass,
        {"light.tv": later},
    )

    assert recorded == {"light.tv": (set(), True)}


@pytest.mark.usefixtures("recorder_mock")
async def test_row_without_a_state_means_no_whole_history(
    hass: HomeAssistant,
) -> None:
    """Test a row the recorder kept without a state leaves a gap."""
    await _record(hass, "light.tv", "dimmed", "on")

    def _blank_the_oldest() -> None:
        with session_scope(hass=hass) as session:
            session.execute(
                update(States).where(States.state == "dimmed").values(state=None)
            )

    await get_instance(hass).async_add_executor_job(_blank_the_oldest)

    recorded = await get_instance(hass).async_add_executor_job(
        state_checking._read_recorded_states,  # noqa: SLF001
        hass,
        {"light.tv": None},
    )

    assert recorded == {"light.tv": ({"on"}, False)}


@pytest.mark.usefixtures("recorder_mock")
async def test_answer_dropped_while_reading_news_is_not_continued(
    hass: HomeAssistant,
    count_recorder_reads: list[dict[str, float | None]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test news read for an answer dropped meanwhile does not bring it back.

    The entity showed a new state while the recorder was read, so its answer
    went, and only a full read can tell the whole story again.
    """
    await _record(hass, "light.tv", "on")
    assert await async_unknown_states(hass, {("light.tv", "dimmed")})
    asking = state_checking._async_ask_the_recorder  # noqa: SLF001

    async def _new_state_meanwhile(hass: HomeAssistant, previous: dict) -> None:
        state_checking._knowledge(hass, "light.tv").see("off")  # noqa: SLF001
        await asking(hass, previous)

    monkeypatch.setattr(state_checking, "_async_ask_the_recorder", _new_state_meanwhile)
    await async_unknown_states(hass, {("light.tv", "dimmed")})
    assert count_recorder_reads[-1]["light.tv"] is not None

    assert hass.data[DATA_STATE_KNOWLEDGE]["light.tv"].answer is None
