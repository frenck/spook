"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import callback, split_entity_id, valid_entity_id
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_filtering import async_get_all_entity_ids
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant

# The built-in agent's ID, which looks like any entity's. Written out rather
# than imported: importing anything from conversation or assist_pipeline
# pulls in libraries only installed where Assist is used, and Spook has to
# load everywhere.
HOME_ASSISTANT_AGENT = "conversation.home_assistant"

# Each step of a pipeline, where it keeps its engine, and the domain an
# engine for it has when it is an entity.
PIPELINE_ENGINES = {
    "conversation_engine": ("conversation", "conversation agent"),
    "stt_engine": ("stt", "speech-to-text"),
    "tts_engine": ("tts", "text-to-speech"),
    "wake_word_entity": ("wake_word", "wake word"),
}


def _async_get_pipelines(hass: HomeAssistant) -> list[Any]:
    """Return the Assist pipelines.

    Imported here, and only called once Assist is set up, for the same reason
    the agent's ID is written out above: the module needs libraries that are
    only there when Assist is.
    """
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.assist_pipeline.pipeline import (  # noqa: PLC0415
        async_get_pipelines,
    )

    return async_get_pipelines(hass)


def _async_get_pipeline_store(hass: HomeAssistant) -> Any:
    """Return the collection Assist keeps its pipelines in.

    Imported here for the same reason as above.
    """
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.assist_pipeline.pipeline import (  # noqa: PLC0415
        KEY_ASSIST_PIPELINE,
    )

    return hass.data[KEY_ASSIST_PIPELINE].pipeline_store


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds Assist pipelines using an engine that is gone.

    A pipeline names the agent and the speech, voice and wake word engines it
    uses, and nothing tidies that up when one of them is removed. The next
    voice command fails with an error about a missing provider, and nothing
    before that points at the pipeline.

    Only values shaped like an entity are checked. The same fields can hold
    older provider IDs, like `cloud`, and there is no reliable way to tell
    whether one of those is still around, so they are left alone rather than
    guessed at.
    """

    domain = "assist_pipeline"
    repair = "unknown_engines"
    inspect_events = {
        EVENT_HOMEASSISTANT_STARTED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    automatically_clean_up_issues = True

    _following_pipelines = False

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        if self.domain not in self.hass.config.components:
            return  # Not set up (yet); there are no pipelines to read.

        self._async_follow_pipeline_changes()

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass)

        for pipeline in _async_get_pipelines(self.hass):
            self.possible_issue_ids.add(pipeline.id)

            unknown = {
                step: engine
                for field, (domain, step) in PIPELINE_ENGINES.items()
                if (engine := getattr(pipeline, field))
                # The built-in agent is always there when Assist is. Its ID
                # looks like any entity's, and is not worth the risk.
                and engine != HOME_ASSISTANT_AGENT
                and valid_entity_id(engine)
                and split_entity_id(engine)[0] == domain
                # Compared with the entities as they are. The shared filter
                # also counts the name of any action as known, which is right
                # for a script, but an engine is never an action.
                and engine not in known_entity_ids
            }
            if not unknown:
                continue

            self.async_create_issue(
                issue_id=pipeline.id,
                references=set(unknown.values()),
                translation_placeholders={
                    "pipeline": pipeline.name,
                    "engines": "\n".join(
                        async_describe_unknown_entities(
                            self.hass, [engine], note=f"the {step}"
                        )
                        for step, engine in unknown.items()
                    ),
                },
            )

    @callback
    def _async_follow_pipeline_changes(self) -> None:
        """Inspect again whenever a pipeline is added, changed, or deleted.

        Editing or deleting a pipeline fires no event on the bus, so the
        issue for a pipeline somebody just fixed would otherwise stay until
        something unrelated came along. Started from the first inspection
        that finds Assist set up, because the store does not exist before.
        """
        if self._following_pipelines:
            return
        self._following_pipelines = True

        async def _pipelines_changed(_changes: Iterable[Any]) -> None:
            await self.inspect_debouncer.async_call()

        self._event_subs.add(
            _async_get_pipeline_store(self.hass).async_add_change_set_listener(
                _pipelines_changed
            )
        )
