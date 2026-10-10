"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING

from homeassistant.components.homeassistant.exposed_entities import (
    async_listen_entity_updates,
    async_should_expose,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    intent,
)
from homeassistant.util import slugify

from ....const import LOGGER
from ....repairs import INSPECTION_YIELD_INTERVAL, AbstractSpookRepair

if TYPE_CHECKING:
    from collections.abc import Collection

    from homeassistant.core import State

# The name Assist goes by in the exposure settings, and the one it asks the
# matcher about. Written out: importing anything from conversation pulls in
# hassil, which is not there in every environment, the tests' for one.
ASSISTANT = "conversation"


def _normalize(name: str) -> str:
    """Return a name the way Assist compares it.

    The same as core's own `_normalize_name` in `helpers/intent.py`, which is
    private. Two names that come out the same here are one name to Assist.
    """
    return name.strip().casefold()


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds names Assist cannot tell apart.

    Assist hears a name, and then picks the entity by it among everything
    exposed to it. When more than one answers to that name, the only thing
    it uses to choose is the area: the one asked for, or the one the voice
    satellite is in. Two of them in the same area, or one without an area at
    all, cannot be picked out by that name from anywhere. Assist answers that
    more than one device has that name, and nothing says which ones.

    Whether a name can be picked out is asked of core's own matcher, once
    for every area a voice satellite could be in. Only a name it refuses
    from every one of them is reported, so a pair Assist sorts out by area
    is left alone.
    """

    domain = "conversation"
    repair = "assist_duplicate_names"
    inspect_events = {
        EVENT_HOMEASSISTANT_STARTED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
        dr.EVENT_DEVICE_REGISTRY_UPDATED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    # An entity without a unique ID never touches the entity registry, but
    # Assist knows it by its state's name all the same.
    inspect_on_entity_added_or_removed = True
    automatically_clean_up_issues = True

    _following_exposure = False

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        if ASSISTANT not in self.hass.config.components:
            return  # No Assist, so nobody asks for anything by name.

        self._async_follow_exposure_changes()

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        for name, states in (await self._async_exposed_names()).items():
            # A name only one entity answers to is never in doubt.
            if len(states) < 2:  # noqa: PLR2004
                continue

            areas, singled_out = self._async_ask_assist(name, states)
            if singled_out >= set(states):
                continue

            entity_ids = sorted(states)
            self.async_create_issue(
                issue_id=slugify(_normalize(name)) or "name",
                references=entity_ids,
                translation_placeholders={
                    "name": name,
                    "entities": "\n".join(
                        f"- `{entity_id}` ({area.name})"
                        if (area := areas.get(entity_id))
                        else f"- `{entity_id}`"
                        for entity_id in entity_ids
                    ),
                },
            )

    @callback
    def _async_follow_exposure_changes(self) -> None:
        """Look again whenever something is exposed to Assist or hidden from it.

        Doing that for an entity with a unique ID updates the entity
        registry, which the events above cover. One without a unique ID keeps
        the setting elsewhere, and only these listeners hear about it. Started
        from the first inspection that finds Assist set up, because the
        settings are only there once Assist is.
        """
        if self._following_exposure:
            return
        self._following_exposure = True

        @callback
        def _async_exposure_changed() -> None:
            self.inspect_debouncer.async_schedule_call()

        self._event_subs.add(
            async_listen_entity_updates(self.hass, ASSISTANT, _async_exposure_changed)
        )

    async def _async_exposed_names(self) -> dict[str, dict[str, State]]:
        """Return every name Assist knows, with the entities answering to it.

        Read the way Assist reads them: every state, only when exposed, and
        by the names and aliases core hands Assist for it. Keyed by one of
        the names as written, the first in alphabetical order, so the issue
        shows the same one each time.
        """
        by_normalized: dict[str, dict[str, State]] = defaultdict(dict)
        written: dict[str, set[str]] = defaultdict(set)

        for index, state in enumerate(self.hass.states.async_all()):
            if index and index % INSPECTION_YIELD_INTERVAL == 0:
                await asyncio.sleep(0)

            if not async_should_expose(self.hass, ASSISTANT, state.entity_id):
                continue

            entry = self.entity_registry.async_get(state.entity_id)
            for name in intent.async_get_entity_aliases(self.hass, entry, state=state):
                normalized = _normalize(name)

                # Assist drops punctuation before it listens for a name, and
                # skips a name that leaves nothing. Nobody can say it.
                if not any(character.isalnum() for character in normalized):
                    continue

                by_normalized[normalized][state.entity_id] = state
                written[normalized].add(name.strip())

        return {
            min(written[normalized]): states
            for normalized, states in by_normalized.items()
        }

    @callback
    def _async_ask_assist(
        self, name: str, states: dict[str, State]
    ) -> tuple[dict[str, ar.AreaEntry | None], set[str]]:
        """Ask core's matcher which of these it can pick out by this name.

        Asked as Assist asks it: by name, among what is exposed, preferring
        the area the voice satellite is in. Once without a satellite area,
        and once for every area there is. Naming an area in the sentence
        never narrows it further than a satellite in that same area does,
        so these are all the chances Assist has.

        Also returns the area core placed each entity in, which follows the
        device when the entity has none of its own.
        """
        areas: dict[str, ar.AreaEntry | None] = {}

        @callback
        def _area_filter(
            candidate: intent.MatchTargetsCandidate, area_ids: Collection[str]
        ) -> bool:
            # Core's own filter, noting down where it put each entity.
            areas[candidate.state.entity_id] = candidate.area
            return candidate.area is not None and candidate.area.id in area_ids

        constraints = intent.MatchTargetsConstraints(name=name, assistant=ASSISTANT)
        satellite_areas: list[str | None] = [
            None,
            *(area.id for area in self.area_registry.async_list_areas()),
        ]

        singled_out: set[str] = set()
        for satellite_area in satellite_areas:
            result = intent.async_match_targets(
                self.hass,
                constraints,
                intent.MatchTargetsPreferences(area_id=satellite_area),
                states=list(states.values()),
                area_candidate_filter=_area_filter,
            )
            if result.is_match and len(result.states) == 1:
                singled_out.add(result.states[0].entity_id)

        return areas, singled_out
