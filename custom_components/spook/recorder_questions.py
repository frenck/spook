"""Spook - Your homie. Asking the recorder, and not waiting on it for good.

Repairs look one at a time, so a repair waiting on the database holds up
every other one behind it. A question the recorder never answers would stop
Spook from noticing anything at all, for as long as Home Assistant runs.

Giving up on the wait does not stop the question. It keeps running in one
of the few threads the recorder reads with, the same ones the history and
logbook of the frontend read with. So Spook asks one question at a time,
and while one it gave up on is still running, it asks nothing new: every
one more would take another of those threads, until nobody's history graphs
load any more.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Final

from homeassistant.helpers.recorder import (
    DATA_INSTANCE,
    async_migration_in_progress,
    get_instance,
)
from homeassistant.util.hass_dict import HassKey

from .const import LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

# How long Spook waits for the recorder to answer one question. Long enough
# for a big database on slow storage to get there, short enough that the
# repairs waiting their turn behind it are not held up for long.
RECORDER_ANSWERS_WITHIN: Final = 60

# Questions Spook stopped waiting for that are still running. Kept with Home
# Assistant rather than with Spook: a reload of Spook does not free the
# threads they hold.
DATA_UNANSWERED_QUESTIONS: HassKey[set[asyncio.Future[Any]]] = HassKey(
    "spook_unanswered_recorder_questions"
)

# Whose turn it is to ask. Repairs take turns looking already, but a fix
# flow asks whenever somebody presses its button, and after a reload of
# Spook a round of the setup before it can still be waiting for its answer.
DATA_ONE_QUESTION_AT_A_TIME: HassKey[asyncio.Lock] = HassKey(
    "spook_one_recorder_question_at_a_time"
)


class RecorderDidNotAnswer(Exception):  # noqa: N818
    """Raised when the recorder did not answer Spook in time.

    Also when an earlier question it did not answer in time is still
    running, and Spook did not ask at all. The reason is Spook's own words
    and never names anything a person chose.
    """


def recorder_can_answer(hass: HomeAssistant) -> bool:
    """Return whether there is a recorder to ask, and it is not busy migrating."""
    return DATA_INSTANCE in hass.data and not async_migration_in_progress(hass)


async def async_ask_in_time[AnswerT](
    hass: HomeAssistant, job: Callable[..., AnswerT], *args: Any
) -> AnswerT:
    """Run a job in the recorder's threads, and wait a limited time for it.

    What the job returns or raises comes back unchanged. Raises
    `RecorderDidNotAnswer` when it did not finish in time, or when it was
    not asked at all: an earlier question Spook gave up on is still running,
    or another one took the whole time.
    """
    _refuse_while_unanswered(hass)

    # The one limit covers waiting for the turn to ask as well.
    answer_by = hass.loop.time() + RECORDER_ANSWERS_WITHIN
    one_at_a_time = hass.data.setdefault(DATA_ONE_QUESTION_AT_A_TIME, asyncio.Lock())
    try:
        async with asyncio.timeout_at(answer_by):
            await one_at_a_time.acquire()
    except TimeoutError:
        msg = "The recorder was busy with an earlier question"
        raise RecorderDidNotAnswer(msg) from None

    try:
        # The one before this may have been given up on just now.
        _refuse_while_unanswered(hass)

        # The recorder hands back a future already, which this leaves as it
        # is. Kept under a name, as it is what says when the thread is done.
        question = asyncio.ensure_future(
            get_instance(hass).async_add_executor_job(job, *args)
        )

        # Waited for rather than awaited under a time limit: running out of
        # time then leaves the question itself alone. Cancelled, it would no
        # longer say when its thread is done.
        try:
            await asyncio.wait({question}, timeout=answer_by - hass.loop.time())
        except asyncio.CancelledError:
            # Spook stopped waiting, unloaded or Home Assistant stopping. The
            # question holds its thread all the same.
            if not question.done():
                _async_leave_unanswered(hass, question)

            # Done the moment the wait was called off, and nobody is left to
            # hear how it went. Its failure is taken, or it would be logged
            # as an error that was never retrieved.
            elif not question.cancelled():
                question.exception()

            raise

        if question.done():
            return question.result()

        _async_leave_unanswered(hass, question)
        LOGGER.warning(
            "The recorder did not answer Spook within %s seconds. Spook carries "
            "on without it, and asks again once it has answered",
            RECORDER_ANSWERS_WITHIN,
        )
        msg = f"The recorder did not answer within {RECORDER_ANSWERS_WITHIN} seconds"
        raise RecorderDidNotAnswer(msg)
    finally:
        one_at_a_time.release()


def _refuse_while_unanswered(hass: HomeAssistant) -> None:
    """Raise when a question Spook gave up on is still running."""
    if not hass.data.get(DATA_UNANSWERED_QUESTIONS):
        return

    LOGGER.debug("Spook did not ask the recorder: an earlier question is still running")
    msg = "An earlier question to the recorder is still not answered"
    raise RecorderDidNotAnswer(msg)


def _async_leave_unanswered(hass: HomeAssistant, question: asyncio.Future[Any]) -> None:
    """Remember a question that is still running, until it is done."""
    unanswered = hass.data.setdefault(DATA_UNANSWERED_QUESTIONS, set())
    unanswered.add(question)

    def _answered_at_last(answered: asyncio.Future[Any]) -> None:
        unanswered.discard(answered)

        # Taken, so a failure nobody waits for any more is not logged as an
        # error that was never retrieved. Nobody acts on this answer either.
        failure = None if answered.cancelled() else answered.exception()
        LOGGER.debug(
            "The recorder answered a question Spook stopped waiting for",
            exc_info=failure,
        )

    question.add_done_callback(_answered_at_last)
