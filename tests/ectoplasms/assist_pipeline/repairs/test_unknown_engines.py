"""Tests for the Assist pipeline unknown engines repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.spook.ectoplasms.assist_pipeline.repairs import (
    unknown_engines,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


def _pipeline(**engines: str | None) -> SimpleNamespace:
    """Return a pipeline, with the built-in agent and no engines unless told.

    A stand-in with the fields the repair reads. Core's own pipeline class
    lives in a module that needs libraries only installed where Assist is
    used, which the test environment is not.
    """
    return SimpleNamespace(
        id="kitchen",
        name="Kitchen voice",
        conversation_engine=engines.get(
            "conversation_engine", "conversation.home_assistant"
        ),
        stt_engine=engines.get("stt_engine"),
        tts_engine=engines.get("tts_engine"),
        wake_word_entity=engines.get("wake_word_entity"),
    )


# pylint: disable-next=too-few-public-methods
class _FakeStore:
    """The part of Assist's pipeline store the repair uses: its listeners."""

    def __init__(self) -> None:
        """Start without listeners."""
        self.listeners: list[Any] = []

    def async_add_change_set_listener(self, listener: Any) -> Any:
        """Remember a listener, and hand back how to forget it."""
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)


async def _inspect(
    hass: HomeAssistant,
    *pipelines: SimpleNamespace,
    repair: unknown_engines.SpookRepair | None = None,
    store: _FakeStore | None = None,
) -> unknown_engines.SpookRepair:
    """Inspect these pipelines, with Assist set up."""
    hass.config.components.add("assist_pipeline")
    repair = repair or unknown_engines.SpookRepair(hass)
    with (
        patch.object(unknown_engines, "_async_get_pipelines", return_value=pipelines),
        patch.object(
            unknown_engines,
            "_async_get_pipeline_store",
            return_value=store or _FakeStore(),
        ),
    ):
        await repair.async_inspect()
    return repair


async def test_a_removed_agent_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The pipeline keeps naming an agent that is not there anymore."""
    await _inspect(hass, _pipeline(conversation_engine="conversation.openai"))

    issue = async_issue_about(issue_registry, "unknown_engines_kitchen")
    assert issue
    assert not issue.is_fixable
    assert issue.translation_placeholders
    assert issue.translation_placeholders["pipeline"] == "Kitchen voice"
    assert (
        "`conversation.openai` (the conversation agent)"
        in issue.translation_placeholders["engines"]
    )


async def test_every_step_is_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Agent, speech, voice and wake word, each named for what it does."""
    await _inspect(
        hass,
        _pipeline(
            conversation_engine="conversation.gone",
            stt_engine="stt.whisper",
            tts_engine="tts.piper",
            wake_word_entity="wake_word.openwakeword",
        ),
    )

    issue = async_issue_about(issue_registry, "unknown_engines_kitchen")
    assert issue
    assert issue.translation_placeholders
    engines = issue.translation_placeholders["engines"]
    for line in (
        "`conversation.gone` (the conversation agent)",
        "`stt.whisper` (the speech-to-text)",
        "`tts.piper` (the text-to-speech)",
        "`wake_word.openwakeword` (the wake word)",
    ):
        assert line in engines


async def test_engines_that_exist_are_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Nothing to report while every engine is there."""
    hass.states.async_set("stt.whisper", "unknown")
    hass.states.async_set("tts.piper", "unknown")

    await _inspect(hass, _pipeline(stt_engine="stt.whisper", tts_engine="tts.piper"))

    assert async_issue_about(issue_registry, "unknown_engines_kitchen") is None


@pytest.mark.parametrize(
    "engines",
    [
        # The built-in agent, whose ID looks like an entity's.
        {"conversation_engine": "conversation.home_assistant"},
        # Older provider names, which are not entities at all.
        {"stt_engine": "cloud", "tts_engine": "cloud"},
        # Shaped like an entity, but not one of the domain for that step.
        {"stt_engine": "sensor.not_an_engine"},
        # Nothing picked for a step.
        {"stt_engine": None, "tts_engine": None, "wake_word_entity": None},
    ],
)
async def test_what_is_not_an_engine_entity_is_not_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    engines: dict[str, str | None],
) -> None:
    """Only what can be told to be gone is reported, the rest is left alone."""
    await _inspect(hass, _pipeline(**engines))

    assert async_issue_about(issue_registry, "unknown_engines_kitchen") is None


async def test_nothing_happens_without_assist(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Assist not set up (yet) means there are no pipelines to read."""
    with patch.object(
        unknown_engines, "_async_get_pipelines", side_effect=AssertionError
    ):
        await unknown_engines.SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


async def test_an_engine_named_like_an_action_is_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An engine is never an action, so an action by that name proves nothing."""
    hass.services.async_register("conversation", "process", AsyncMock())

    await _inspect(hass, _pipeline(conversation_engine="conversation.process"))

    assert async_issue_about(issue_registry, "unknown_engines_kitchen")


async def test_a_pipeline_change_inspects_again(hass: HomeAssistant) -> None:
    """Editing or deleting a pipeline fires nothing on the bus.

    Without following the store, the issue for a pipeline somebody just fixed
    would stay until something unrelated came along.
    """
    store = _FakeStore()
    repair = await _inspect(hass, _pipeline(), store=store)
    repair.inspect_debouncer = AsyncMock()

    await store.listeners[0]([("updated", "kitchen", {})])

    repair.inspect_debouncer.async_call.assert_awaited_once()


async def test_the_store_is_followed_once_and_let_go_on_deactivate(
    hass: HomeAssistant,
) -> None:
    """Every inspection does not add another listener, and none outlive it."""
    store = _FakeStore()
    repair = await _inspect(hass, _pipeline(), store=store)
    await _inspect(hass, _pipeline(), repair=repair, store=store)
    assert len(store.listeners) == 1

    # Normally made when the repair is activated, which this test skips.
    repair.inspect_debouncer = MagicMock()
    await repair.async_deactivate()

    assert not store.listeners
