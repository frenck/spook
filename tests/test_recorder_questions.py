"""Tests for asking the recorder, and not waiting on it for good.

Repairs look one at a time, and a question the recorder never answered held
the turn for good: every other repair queued behind it, and nothing was
looked at again. Giving up on the wait does not stop the question, which
keeps one of the recorder's few read threads, the ones the history graphs
of the frontend need too. So these pin both halves: Spook stops waiting,
and asks nothing new until what it gave up on is done.
"""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

import asyncio
from datetime import timedelta
import gc
import logging
import threading
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.components.recorder.common import (
    async_wait_recording_done,
)
from sqlalchemy.exc import OperationalError

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.light import LightEntity

from custom_components.spook import (
    attribute_checking,
    attribute_value_checking,
    recorder_questions,
    state_checking,
    statistics_sources,
)
from custom_components.spook.attribute_checking import (
    DATA_ATTRIBUTE_KNOWLEDGE,
    UnknownAttribute,
    async_unknown_attributes,
)
from custom_components.spook.attribute_value_checking import (
    DATA_ATTRIBUTE_VALUE_KNOWLEDGE,
    UnknownAttributeValue,
    async_unknown_attribute_values,
)
from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.recorder.repairs import orphaned_statistics
from custom_components.spook.recorder_questions import (
    DATA_UNANSWERED_QUESTIONS,
    RECORDER_ANSWERS_WITHIN,
    RecorderDidNotAnswer,
    async_ask_in_time,
)
from custom_components.spook.reference_extraction import AttributeValue
from custom_components.spook.repairs import (
    AbstractSpookRepair,
    LookOutcome,
    SpookRepairManager,
)
from custom_components.spook.state_checking import (
    DATA_STATE_KNOWLEDGE,
    UnknownState,
    async_unknown_states,
)
from tests.entity_objects import give_entity_objects

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

# Short enough that giving up does not make the tests slow, on a clock that
# really runs. The tests on a frozen clock move it past the real limit.
_SOON = 0.05

_NAMED_BY_SOMEBODY = "sensor.what_somebody_named_it"


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


class _HeldBack:
    """A database that does not answer until let go, counting what it is asked."""

    def __init__(self) -> None:
        """Start out holding on."""
        self.calls = 0
        self.started = threading.Event()
        self.let_go = threading.Event()
        self.finished = threading.Event()

    def wrap[AnswerT](
        self, job: Callable[..., AnswerT], *, fail: Exception | None = None
    ) -> Callable[..., AnswerT]:
        """Return the job, held back until let go, and failing if told to."""

        def _held_back(*args: Any) -> AnswerT:
            self.calls += 1
            self.started.set()
            # Bounded, so a test that forgets to let go fails, and does not
            # hang the run.
            self.let_go.wait(timeout=30)
            self.finished.set()
            if fail is not None:
                raise fail
            return job(*args)

        return _held_back

    async def async_started(self, hass: HomeAssistant) -> None:
        """Wait until the job runs in the recorder's thread."""
        assert await hass.async_add_executor_job(self.started.wait, 5)


@pytest.fixture(name="held_back")
def fixture_held_back() -> Iterator[_HeldBack]:
    """Return a database that does not answer, and let it go afterwards."""
    held_back = _HeldBack()
    yield held_back
    held_back.let_go.set()


@pytest.fixture(name="answers_soon")
def fixture_answers_soon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give up on the recorder after a moment instead of a minute."""
    monkeypatch.setattr(recorder_questions, "RECORDER_ANSWERS_WITHIN", _SOON)


def _unanswered(hass: HomeAssistant) -> set[asyncio.Future[Any]]:
    """Return the questions Spook gave up on that are still running."""
    return hass.data.get(DATA_UNANSWERED_QUESTIONS, set())


async def _async_until_answered(hass: HomeAssistant) -> None:
    """Wait for every question Spook gave up on to be done.

    On the futures themselves, not on a clock: some of these tests freeze it.
    """
    if unanswered := set(_unanswered(hass)):
        await asyncio.wait(unanswered)
    await asyncio.sleep(0)


def _answer(*args: Any) -> tuple[Any, ...]:
    """Answer with what was asked."""
    return args


def _count_what_the_recorder_is_handed(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> list[Callable[..., Any]]:
    """Return a list that gets every job the moment it goes to the recorder."""
    handed_over: list[Callable[..., Any]] = []
    instance = recorder_questions.get_instance(hass)
    hand_over = instance.async_add_executor_job

    def _counting(job: Callable[..., Any], *args: Any) -> asyncio.Future[Any]:
        handed_over.append(job)
        return hand_over(job, *args)

    monkeypatch.setattr(instance, "async_add_executor_job", _counting)
    return handed_over


# The helper on its own.


@pytest.mark.usefixtures("recorder_mock")
async def test_an_answer_in_time_comes_back_unchanged(hass: HomeAssistant) -> None:
    """Test what the job returns is what the caller gets, asked once."""
    asked: list[tuple[Any, ...]] = []

    def _job(*args: Any) -> str:
        asked.append(args)
        return "answer"

    assert await async_ask_in_time(hass, _job, 1, 2) == "answer"
    assert asked == [(1, 2)]
    assert not _unanswered(hass)


@pytest.mark.usefixtures("recorder_mock")
async def test_a_failure_in_time_comes_back_unchanged(hass: HomeAssistant) -> None:
    """Test a database error is passed on as it is, for the caller to handle."""
    failure = OperationalError("SELECT", {}, Exception("database is locked"))

    def _job() -> None:
        raise failure

    with pytest.raises(OperationalError) as raised:
        await async_ask_in_time(hass, _job)

    assert raised.value is failure
    assert not _unanswered(hass)


@pytest.mark.usefixtures("recorder_mock")
async def test_a_job_timing_out_by_itself_is_not_the_recorder_being_slow(
    hass: HomeAssistant,
) -> None:
    """Test a job that raises a timeout of its own answered, and in time."""

    def _job() -> None:
        message = "the job's own"
        raise TimeoutError(message)

    with pytest.raises(TimeoutError, match="the job's own"):
        await async_ask_in_time(hass, _job)

    assert not _unanswered(hass)


@pytest.mark.usefixtures("recorder_mock", "answers_soon")
async def test_too_slow_is_given_up_on_while_it_keeps_running(
    hass: HomeAssistant, held_back: _HeldBack
) -> None:
    """Test the wait ends after the limit, and the question is still running."""
    with pytest.raises(RecorderDidNotAnswer, match="did not answer within"):
        await async_ask_in_time(hass, held_back.wrap(_answer))

    assert held_back.started.is_set()
    assert not held_back.finished.is_set()
    assert len(_unanswered(hass)) == 1


@pytest.mark.usefixtures("recorder_mock", "answers_soon")
async def test_given_up_and_finished_since_is_told_from_still_running(
    hass: HomeAssistant, held_back: _HeldBack
) -> None:
    """Test once the question Spook gave up on is done, asking works again."""
    with pytest.raises(RecorderDidNotAnswer):
        await async_ask_in_time(hass, held_back.wrap(_answer))

    # Given up, still running: not asked.
    with pytest.raises(RecorderDidNotAnswer, match="still not answered"):
        await async_ask_in_time(hass, _answer, "too soon")

    held_back.let_go.set()
    await _async_until_answered(hass)

    # Given up, finished since: asked, and answered.
    assert not _unanswered(hass)
    assert await async_ask_in_time(hass, _answer, "again") == ("again",)


@pytest.mark.usefixtures("recorder_mock")
async def test_never_more_than_one_lost_question_in_the_recorder(
    hass: HomeAssistant,
    held_back: _HeldBack,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a database that never answers gets one of Spook's questions, not five.

    Every question asked again would take one more of the recorder's read
    threads, until the history graphs of the frontend found none left. The
    ones turned away do not wait either: they hold up the other repairs just
    as much.
    """
    limit = 0.5
    monkeypatch.setattr(recorder_questions, "RECORDER_ANSWERS_WITHIN", limit)
    caplog.set_level(logging.DEBUG, logger="custom_components.spook")
    never_answers = held_back.wrap(_answer)

    with pytest.raises(RecorderDidNotAnswer):
        await async_ask_in_time(hass, never_answers, _NAMED_BY_SOMEBODY)

    for _ in range(4):
        async with asyncio.timeout(limit / 2):
            with pytest.raises(RecorderDidNotAnswer):
                await async_ask_in_time(hass, never_answers, _NAMED_BY_SOMEBODY)

    assert held_back.calls == 1

    # Said once, and in words that name nothing of the house.
    warnings = [
        record for record in caplog.records if record.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    assert "did not answer Spook within 0.5 seconds" in warnings[0].getMessage()
    assert _NAMED_BY_SOMEBODY not in caplog.text


@pytest.mark.usefixtures("recorder_mock", "answers_soon")
async def test_a_lost_question_failing_later_leaves_nothing_behind(
    hass: HomeAssistant,
    held_back: _HeldBack,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failure nobody waits for any more is not logged as never retrieved."""
    caplog.set_level(logging.DEBUG, logger="custom_components.spook")
    failure = OperationalError("SELECT", {}, Exception("database is locked"))
    with pytest.raises(RecorderDidNotAnswer):
        await async_ask_in_time(hass, held_back.wrap(_answer, fail=failure))

    held_back.let_go.set()
    await _async_until_answered(hass)
    gc.collect()
    await asyncio.sleep(0)

    assert not _unanswered(hass)
    assert "never retrieved" not in caplog.text
    # Nor by any other name: some Python versions report a failure behind a
    # wait that was given up on through the loop's own error handler.
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    # Said, but only for whoever turned on debug logging: nobody waits for
    # this answer any more.
    (answered,) = (
        record
        for record in caplog.records
        if "answered a question Spook stopped waiting for" in record.getMessage()
    )
    assert answered.levelno == logging.DEBUG
    assert answered.exc_info
    assert answered.exc_info[1] is failure


async def test_a_question_failing_as_the_wait_is_called_off_leaves_nothing_behind(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failure that lands the moment the round is called off is taken.

    The question is done by then, so nothing waits for it and nothing counts
    it as still running. Its failure has nobody left to hear it either.
    """
    failure = OperationalError("SELECT", {}, Exception("database is locked"))
    # Held in a list, so the test can let go of the last reference to it.
    # An exception nobody took is only reported once its future is collected.
    questions: list[asyncio.Future[None]] = [hass.loop.create_future()]
    questions[0].set_exception(failure)

    monkeypatch.setattr(
        recorder_questions,
        "get_instance",
        lambda _hass: SimpleNamespace(async_add_executor_job=lambda *_: questions[0]),
    )

    async def _called_off(*_: Any, **__: Any) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(recorder_questions.asyncio, "wait", _called_off)

    with pytest.raises(asyncio.CancelledError):
        await async_ask_in_time(hass, _answer)

    monkeypatch.undo()
    questions.clear()
    gc.collect()
    await asyncio.sleep(0)

    assert not _unanswered(hass)
    assert "never retrieved" not in caplog.text
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


@pytest.mark.usefixtures("recorder_mock")
async def test_questions_asked_at_the_same_time_take_turns(
    hass: HomeAssistant,
    held_back: _HeldBack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test two callers at once never have two questions in the recorder.

    Repairs take turns looking, but a fix flow asks whenever somebody
    presses its button, and after a reload a round of the setup before can
    still be waiting. Each one at once would be another read thread taken.
    """
    handed_over = _count_what_the_recorder_is_handed(hass, monkeypatch)

    def _second_job() -> str:
        return "second answer"

    first = hass.async_create_task(
        async_ask_in_time(hass, held_back.wrap(_answer), "first"), eager_start=False
    )
    await held_back.async_started(hass)

    second = hass.async_create_task(
        async_ask_in_time(hass, _second_job), eager_start=False
    )
    for _ in range(5):
        await asyncio.sleep(0)

    # Waiting its turn, and not handed to the recorder yet. Counted where it
    # is handed over: a job handed over early may not have run by now.
    assert not second.done()
    assert len(handed_over) == 1

    held_back.let_go.set()
    assert await first == ("first",)
    assert await second == "second answer"
    assert len(handed_over) == 1 + 1
    assert not _unanswered(hass)


@pytest.mark.usefixtures("recorder_mock", "answers_soon")
async def test_a_question_waiting_behind_one_given_up_on_is_not_asked(
    hass: HomeAssistant,
    held_back: _HeldBack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a caller waiting its turn does not ask once the one ahead is lost.

    Two callers at the same moment, and a recorder that answers neither:
    the one waiting must not take a second thread when its turn comes.
    """
    handed_over = _count_what_the_recorder_is_handed(hass, monkeypatch)

    first = hass.async_create_task(
        async_ask_in_time(hass, held_back.wrap(_answer)), eager_start=False
    )
    await held_back.async_started(hass)

    # The second has all the time it needs, so running out of it while
    # waiting its turn is not what stops it.
    monkeypatch.setattr(recorder_questions, "RECORDER_ANSWERS_WITHIN", 30)
    second = hass.async_create_task(async_ask_in_time(hass, _answer), eager_start=False)

    with pytest.raises(RecorderDidNotAnswer, match="did not answer within"):
        await first
    with pytest.raises(RecorderDidNotAnswer, match="is still not answered"):
        await second

    assert held_back.calls == 1
    assert len(handed_over) == 1
    assert len(_unanswered(hass)) == 1


@pytest.mark.usefixtures("recorder_mock")
async def test_a_question_that_is_done_no_longer_stands_in_the_way(
    hass: HomeAssistant,
) -> None:
    """Test a question given up on stops counting the moment it is done.

    Its place in the list is cleared a moment after it finishes. A caller
    getting in before that must not be turned away over a question that
    holds no thread any more.
    """
    done: asyncio.Future[None] = hass.loop.create_future()
    done.set_result(None)
    hass.data[DATA_UNANSWERED_QUESTIONS] = {done}

    assert await async_ask_in_time(hass, _answer, "asked") == ("asked",)


@pytest.mark.usefixtures("recorder_mock")
async def test_a_turn_that_comes_with_the_time_gone_does_not_ask(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a question whose time is up by its turn is not handed over.

    Handed over then, it would be given up on at once, and count as one the
    recorder did not answer while the recorder never got to it.
    """
    handed_over = _count_what_the_recorder_is_handed(hass, monkeypatch)
    monkeypatch.setattr(recorder_questions, "RECORDER_ANSWERS_WITHIN", 0)

    with pytest.raises(RecorderDidNotAnswer, match="busy with an earlier question"):
        await async_ask_in_time(hass, _answer)

    assert not handed_over
    assert not _unanswered(hass)


@pytest.mark.usefixtures("recorder_mock")
async def test_called_off_while_waiting_counts_as_still_running(
    hass: HomeAssistant, held_back: _HeldBack
) -> None:
    """Test a round called off mid-question leaves the question counted.

    Spook unloading, or Home Assistant stopping, ends the wait. The question
    keeps its thread all the same.
    """
    waiting = hass.async_create_task(
        async_ask_in_time(hass, held_back.wrap(_answer)), eager_start=False
    )
    await held_back.async_started(hass)

    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting

    assert len(_unanswered(hass)) == 1
    with pytest.raises(RecorderDidNotAnswer, match="still not answered"):
        await async_ask_in_time(hass, _answer)

    held_back.let_go.set()
    await _async_until_answered(hass)

    assert await async_ask_in_time(hass, _answer, "again") == ("again",)


# The history readers. Without an answer, what is certain without history is
# still reported, and nothing is remembered as read.


async def _record(hass: HomeAssistant, entity_id: str, *states: tuple) -> None:
    """Set an entity to each of these, and wait for the recorder."""
    for state, attributes in states:
        hass.states.async_set(entity_id, state, attributes)
    await async_wait_recording_done(hass)


@pytest.mark.usefixtures("recorder_mock", "answers_soon")
async def test_attributes_without_an_answer_in_time(
    hass: HomeAssistant,
    held_back: _HeldBack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a slow recorder leaves the attribute check with what is certain."""
    await _record(hass, "sensor.weather_alert", ("1", {"alert": "storm"}))
    monkeypatch.setattr(
        attribute_checking,
        "_read_recorded_attribute_keys",
        held_back.wrap(attribute_checking._read_recorded_attribute_keys),
    )
    asked = {
        ("sensor.weather_alert", "Alert"),
        ("sensor.weather_alert", "nothing"),
    }

    assert await async_unknown_attributes(hass, asked) == {
        UnknownAttribute("sensor.weather_alert", "Alert", "alert"),
    }
    assert hass.data[DATA_ATTRIBUTE_KNOWLEDGE]["sensor.weather_alert"].answer is None

    held_back.let_go.set()
    await _async_until_answered(hass)

    assert await async_unknown_attributes(hass, asked) == {
        UnknownAttribute("sensor.weather_alert", "Alert", "alert"),
        UnknownAttribute("sensor.weather_alert", "nothing", None),
    }


@pytest.mark.usefixtures("recorder_mock", "answers_soon")
async def test_states_without_an_answer_in_time(
    hass: HomeAssistant,
    held_back: _HeldBack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a slow recorder leaves the state check with what is certain."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    await _record(hass, "light.kitchen", ("on", {}), ("off", {}))
    monkeypatch.setattr(
        state_checking,
        "_read_recorded_states",
        held_back.wrap(state_checking._read_recorded_states),
    )
    asked = {("light.kitchen", "On"), ("light.kitchen", "dimmed")}

    assert await async_unknown_states(hass, asked) == {
        UnknownState("light.kitchen", "On", "on"),
    }
    assert hass.data[DATA_STATE_KNOWLEDGE]["light.kitchen"].answer is None

    held_back.let_go.set()
    await _async_until_answered(hass)

    assert await async_unknown_states(hass, asked) == {
        UnknownState("light.kitchen", "On", "on"),
        UnknownState("light.kitchen", "dimmed", None),
    }


@pytest.mark.usefixtures("recorder_mock", "answers_soon")
async def test_attribute_values_without_an_answer_in_time(
    hass: HomeAssistant,
    held_back: _HeldBack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a slow recorder leaves the value check with nothing to report.

    Every finding there needs the whole history.
    """
    climate = "climate.living_room"
    give_entity_objects(hass, climate, kind=ClimateEntity)
    await _record(hass, climate, ("heat", {"hvac_action": "idle"}))
    monkeypatch.setattr(
        attribute_value_checking,
        "_read_recorded_values",
        held_back.wrap(attribute_value_checking._read_recorded_values),
    )
    asked = {(climate, AttributeValue("hvac_action", "Heating"))}

    assert not await async_unknown_attribute_values(hass, asked)
    assert hass.data[DATA_ATTRIBUTE_VALUE_KNOWLEDGE][climate].answer is None

    held_back.let_go.set()
    await _async_until_answered(hass)

    assert await async_unknown_attribute_values(hass, asked) == {
        UnknownAttributeValue(climate, "hvac_action", "Heating", "heating"),
    }


# With an answer from before. It stops where it was read, so without a new
# one it is not the whole history any more.


@pytest.mark.usefixtures("recorder_mock", "answers_soon")
async def test_attributes_do_not_go_by_an_old_answer_without_a_new_one(
    hass: HomeAssistant,
    held_back: _HeldBack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an answer from before is not the whole history when the next fails.

    What the entity went through since that answer is unread. It may well
    have had the attribute by now.
    """
    await _record(hass, "sensor.weather_alert", ("1", {"alert": "storm"}))
    asked = {
        ("sensor.weather_alert", "Alert"),
        ("sensor.weather_alert", "nothing"),
    }
    certain = UnknownAttribute("sensor.weather_alert", "Alert", "alert")
    needs_history = UnknownAttribute("sensor.weather_alert", "nothing", None)

    assert await async_unknown_attributes(hass, asked) == {certain, needs_history}
    before = hass.data[DATA_ATTRIBUTE_KNOWLEDGE]["sensor.weather_alert"].answer
    assert before is not None
    assert before.complete

    monkeypatch.setattr(
        attribute_checking,
        "_read_recorded_attribute_keys",
        held_back.wrap(attribute_checking._read_recorded_attribute_keys),
    )
    assert await async_unknown_attributes(hass, asked) == {certain}

    # Kept as it was, to be added to once the recorder answers again.
    assert hass.data[DATA_ATTRIBUTE_KNOWLEDGE]["sensor.weather_alert"].answer is before

    held_back.let_go.set()
    await _async_until_answered(hass)
    assert await async_unknown_attributes(hass, asked) == {certain, needs_history}


@pytest.mark.usefixtures("recorder_mock", "answers_soon")
async def test_states_do_not_go_by_an_old_answer_without_a_new_one(
    hass: HomeAssistant,
    held_back: _HeldBack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an answer from before is not the whole history when the next fails."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    await _record(hass, "light.kitchen", ("on", {}), ("off", {}))
    asked = {("light.kitchen", "On"), ("light.kitchen", "dimmed")}
    certain = UnknownState("light.kitchen", "On", "on")
    needs_history = UnknownState("light.kitchen", "dimmed", None)

    assert await async_unknown_states(hass, asked) == {certain, needs_history}
    before = hass.data[DATA_STATE_KNOWLEDGE]["light.kitchen"].answer
    assert before is not None
    assert before.complete

    monkeypatch.setattr(
        state_checking,
        "_read_recorded_states",
        held_back.wrap(state_checking._read_recorded_states),
    )
    assert await async_unknown_states(hass, asked) == {certain}
    assert hass.data[DATA_STATE_KNOWLEDGE]["light.kitchen"].answer is before

    held_back.let_go.set()
    await _async_until_answered(hass)
    assert await async_unknown_states(hass, asked) == {certain, needs_history}


@pytest.mark.usefixtures("recorder_mock", "answers_soon")
async def test_attribute_values_do_not_go_by_an_old_answer_without_a_new_one(
    hass: HomeAssistant,
    held_back: _HeldBack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an answer from before is not the whole history when the next fails.

    Every finding there needs the whole history, so nothing is reported.
    """
    climate = "climate.living_room"
    give_entity_objects(hass, climate, kind=ClimateEntity)
    await _record(hass, climate, ("heat", {"hvac_action": "idle"}))
    asked = {(climate, AttributeValue("hvac_action", "Heating"))}
    needs_history = UnknownAttributeValue(climate, "hvac_action", "Heating", "heating")

    assert await async_unknown_attribute_values(hass, asked) == {needs_history}
    before = hass.data[DATA_ATTRIBUTE_VALUE_KNOWLEDGE][climate].answer
    assert before is not None
    assert before.complete

    monkeypatch.setattr(
        attribute_value_checking,
        "_read_recorded_values",
        held_back.wrap(attribute_value_checking._read_recorded_values),
    )
    assert not await async_unknown_attribute_values(hass, asked)
    assert hass.data[DATA_ATTRIBUTE_VALUE_KNOWLEDGE][climate].answer is before

    held_back.let_go.set()
    await _async_until_answered(hass)
    assert await async_unknown_attribute_values(hass, asked) == {needs_history}


# The way it went wrong.


class _ReportingRepair(AbstractSpookRepair):
    """Repair that needs no database, and finds something every time it looks."""

    domain = "mock"
    repair = "mock_reporting"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self.looks = 0

    async def async_inspect(self) -> None:
        """Look, and report what is found."""
        self.looks += 1
        self.async_create_issue(issue_id="found")


async def _let_tasks_run() -> None:
    """Give tasks their turns, without waiting for all of them."""
    for _ in range(10):
        await asyncio.sleep(0)


async def _come_due(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float = 5
) -> None:
    """Let time pass, and what came due in it start."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await _let_tasks_run()


@pytest.mark.usefixtures("recorder_mock")
async def test_a_database_that_never_answers_does_not_stop_the_other_repairs(
    hass: HomeAssistant,
    held_back: _HeldBack,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a repair that needs no database looks while another's question hangs.

    The way it went wrong: the orphaned statistics repair asked the recorder,
    the answer never came, and every other repair waited behind it for as
    long as Home Assistant ran.
    """
    monkeypatch.setattr(
        statistics_sources,
        "validate_statistics",
        held_back.wrap(lambda _hass: {}),
    )
    manager = SpookRepairManager(hass)

    await manager._async_setup_repair_module(orphaned_statistics)
    await _come_due(hass, freezer)
    await held_back.async_started(hass)
    (asking,) = manager.repairs

    await manager._async_setup_repair_module(
        SimpleNamespace(__name__="mock.reporting", SpookRepair=_ReportingRepair)
    )
    reporting = next(
        repair for repair in manager.repairs if isinstance(repair, _ReportingRepair)
    )
    await _come_due(hass, freezer)
    assert reporting.looks == 0

    await _come_due(hass, freezer, RECORDER_ANSWERS_WITHIN + 1)

    assert asking.last_look
    assert asking.last_look.outcome is LookOutcome.COULD_NOT_LOOK
    assert reporting.looks == 1
    assert issue_registry.async_get_issue(DOMAIN, "mock_reporting_found")

    held_back.let_go.set()
    await _async_until_answered(hass)
    await manager.async_on_unload()
