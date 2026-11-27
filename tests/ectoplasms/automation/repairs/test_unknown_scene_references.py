"""Tests for scene references in automations.

Scenes were ignored wholesale, because `scene.create` builds them while an
automation runs and nothing knows about them beforehand. These pin the
narrower rule: a scene some configured action creates is known, any other
missing scene is reported.
"""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

import gc
from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from weakref import WeakKeyDictionary

from homeassistant.components import automation, script
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import callback
from homeassistant.setup import async_setup_component

from custom_components.spook import configuration_cache, entity_filtering
from custom_components.spook.ectoplasms.automation.repairs.unknown_entity_references import (
    SpookRepair,
)
from custom_components.spook.ectoplasms.script.repairs.unknown_entity_references import (
    SpookRepair as ScriptSpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest

    from homeassistant.core import Event, EventStateChangedData, HomeAssistant
    from homeassistant.helpers import issue_registry as ir


async def _inspect(hass: HomeAssistant, actions: list[dict]) -> None:
    """Set up an automation with the given actions and inspect it."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            "automation": [
                {
                    "alias": "Scene test",
                    "triggers": [{"trigger": "event", "event_type": "poke"}],
                    "actions": actions,
                },
            ],
        },
    )
    await hass.async_block_till_done()
    await SpookRepair(hass)._async_inspect_with_cleanup()


def _reported(issue_registry: ir.IssueRegistry) -> str | None:
    """Return the reported entities for the test automation, if any."""
    issue = async_issue_about(
        issue_registry, "automation_unknown_entity_references_automation.scene_test"
    )
    return issue.translation_placeholders["entities"] if issue else None


async def test_missing_scene_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a scene that does not exist is reported."""
    await _inspect(
        hass,
        [{"action": "scene.turn_on", "target": {"entity_id": "scene.deleted"}}],
    )

    assert "scene.deleted" in (_reported(issue_registry) or "")


async def test_existing_scene_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a scene that exists is left alone."""
    hass.states.async_set("scene.movie_night", "scening")

    await _inspect(
        hass,
        [{"action": "scene.turn_on", "target": {"entity_id": "scene.movie_night"}}],
    )

    assert _reported(issue_registry) is None


async def test_scene_created_by_an_action_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a scene the same automation creates is treated as known.

    This is the snapshot-then-restore pattern, and the reason scenes were
    ignored in the first place.
    """
    hass.states.async_set("light.hall", "on")

    await _inspect(
        hass,
        [
            {
                "action": "scene.create",
                "data": {"scene_id": "before", "snapshot_entities": ["light.hall"]},
            },
            {"action": "scene.turn_on", "target": {"entity_id": "scene.before"}},
        ],
    )

    assert _reported(issue_registry) is None


async def test_scene_created_in_a_nested_block_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a scene.create inside a branch still counts."""
    hass.states.async_set("light.hall", "on")

    await _inspect(
        hass,
        [
            {
                "if": [
                    {"condition": "state", "entity_id": "light.hall", "state": "on"}
                ],
                "then": [
                    {
                        "action": "scene.create",
                        "data": {
                            "scene_id": "nested",
                            "snapshot_entities": ["light.hall"],
                        },
                    },
                ],
            },
            {"action": "scene.turn_on", "target": {"entity_id": "scene.nested"}},
        ],
    )

    assert _reported(issue_registry) is None


async def test_templated_scene_id_is_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a templated scene_id does not silence the scene it names.

    Spook cannot know what the template renders to, so the safe answer is to
    keep reporting rather than assume a match.
    """
    hass.states.async_set("light.hall", "on")

    await _inspect(
        hass,
        [
            {
                "action": "scene.create",
                "data": {
                    "scene_id": "{{ 'dynamic' }}",
                    "snapshot_entities": ["light.hall"],
                },
            },
            {"action": "scene.turn_on", "target": {"entity_id": "scene.dynamic"}},
        ],
    )

    assert "scene.dynamic" in (_reported(issue_registry) or "")


async def test_scene_created_with_legacy_data_template_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the legacy `data_template` form is read too.

    Raw configuration has not had `data_template` folded into `data` yet, and
    Home Assistant still accepts it, so a scene created that way has to count.
    """
    hass.states.async_set("light.hall", "on")

    await _inspect(
        hass,
        [
            {
                "service": "scene.create",
                "data_template": {
                    "scene_id": "legacy",
                    "snapshot_entities": ["light.hall"],
                },
            },
            {"action": "scene.turn_on", "target": {"entity_id": "scene.legacy"}},
        ],
    )

    assert _reported(issue_registry) is None


async def test_scene_created_by_a_script_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a scene a script creates counts for an automation that uses it.

    Scripts are scanned as well as automations, because the snapshot and the
    restore do not have to live in the same place.
    """
    hass.states.async_set("light.hall", "on")

    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            "script": {
                "snapshotter": {
                    "sequence": [
                        {
                            "action": "scene.create",
                            "data": {
                                "scene_id": "from_script",
                                "snapshot_entities": ["light.hall"],
                            },
                        },
                    ],
                },
            },
        },
    )
    await hass.async_block_till_done()

    await _inspect(
        hass,
        [{"action": "scene.turn_on", "target": {"entity_id": "scene.from_script"}}],
    )

    assert _reported(issue_registry) is None


async def test_scene_id_in_either_payload_key_counts(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test both payload keys are read, not just whichever comes first.

    A step can carry `data` and `data_template` at once, with the scene_id in
    either. Home Assistant merges them, so preferring one key loses the other.
    """
    hass.states.async_set("light.hall", "on")

    await _inspect(
        hass,
        [
            {
                "service": "scene.create",
                "data": {"snapshot_entities": ["light.hall"]},
                "data_template": {"scene_id": "split"},
            },
            {"action": "scene.turn_on", "target": {"entity_id": "scene.split"}},
        ],
    )

    assert _reported(issue_registry) is None


async def test_scene_created_by_a_broken_automation_is_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a configuration Home Assistant rejected does not vouch for a scene.

    Home Assistant keeps a placeholder entity for an automation it could not
    validate, and that placeholder still carries the raw configuration. It can
    never run, so the scene it would have created does not exist.
    """
    hass.states.async_set("light.hall", "on")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            "automation": [
                {
                    # No triggers key, so validation fails and Home Assistant
                    # keeps an unavailable placeholder for it.
                    "alias": "Broken",
                    "actions": [
                        {
                            "action": "scene.create",
                            "data": {
                                "scene_id": "never_made",
                                "snapshot_entities": ["light.hall"],
                            },
                        },
                    ],
                },
                {
                    "alias": "Scene test",
                    "triggers": [{"trigger": "event", "event_type": "poke"}],
                    "actions": [
                        {
                            "action": "scene.turn_on",
                            "target": {"entity_id": "scene.never_made"},
                        },
                    ],
                },
            ],
        },
    )
    await hass.async_block_till_done()

    await SpookRepair(hass)._async_inspect_with_cleanup()

    assert "scene.never_made" in (_reported(issue_registry) or "")


# A scene the automation below creates, and turns back on.
_SNAPSHOT = {
    "action": "scene.create",
    "data": {"scene_id": "before", "snapshot_entities": ["light.hall"]},
}
_RESTORE = {"action": "scene.turn_on", "target": {"entity_id": "scene.before"}}


def _automation_config(actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a configuration with one automation that has an `id`.

    The `id` is the point: an automation with one is registered, and a reload
    takes it to a restored, unavailable state and back, never to no state.
    """
    return {
        "automation": [
            {
                "id": "scene_test",
                "alias": "Scene test",
                "triggers": [{"trigger": "event", "event_type": "poke"}],
                "actions": actions,
            },
        ],
    }


def _script_config(sequence: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a configuration with one script."""
    return {"script": {"snapshotter": {"sequence": sequence}}}


def _states_coming_or_going(hass: HomeAssistant) -> tuple[list[str], Callable]:
    """Record every entity that gets a first state or loses its last one."""
    came_or_went: list[str] = []

    @callback
    def _came_or_went(data: EventStateChangedData) -> bool:
        return data["old_state"] is None or data["new_state"] is None

    @callback
    def _record(event: Event[EventStateChangedData]) -> None:
        came_or_went.append(event.data["entity_id"])

    unsubscribe = hass.bus.async_listen(
        EVENT_STATE_CHANGED, _record, event_filter=_came_or_went
    )
    return came_or_went, unsubscribe


async def _reload(hass: HomeAssistant, domain: str, config: dict[str, Any]) -> None:
    """Reload ``domain`` the way saving it in the UI does, with ``config``."""
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await hass.services.async_call(domain, "reload", blocking=True)
    await hass.async_block_till_done()


def _script_reported(issue_registry: ir.IssueRegistry) -> str | None:
    """Return the reported entities for the test script, if any."""
    issue = async_issue_about(
        issue_registry, "script_unknown_entity_references_script.snapshotter"
    )
    return issue.translation_placeholders["entities"] if issue else None


async def test_scene_created_after_a_reload_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a `scene.create` an automation gains in a reload counts right away.

    Editing an automation in the UI and saving it is a reload. Nothing comes
    or goes in the registry or the state machine for that, which is all the
    entity IDs cache listens to. The scenes created were cached alongside, so
    the freshly created scene was reported as unknown.
    """
    hass.states.async_set("light.hall", "on")
    unsubscribe_cache = entity_filtering.async_setup_all_entity_ids_cache_invalidation(
        hass
    )
    assert await async_setup_component(hass, automation.DOMAIN, _automation_config([]))
    await hass.async_block_till_done()
    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()

    came_or_went, unsubscribe_states = _states_coming_or_going(hass)
    await _reload(hass, automation.DOMAIN, _automation_config([_SNAPSHOT, _RESTORE]))
    unsubscribe_states()
    await repair._async_inspect_with_cleanup()
    unsubscribe_cache()

    assert not came_or_went
    assert _reported(issue_registry) is None


async def test_scene_no_longer_created_after_a_reload_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a `scene.create` an automation loses in a reload stops counting."""
    hass.states.async_set("light.hall", "on")
    unsubscribe_cache = entity_filtering.async_setup_all_entity_ids_cache_invalidation(
        hass
    )
    assert await async_setup_component(
        hass, automation.DOMAIN, _automation_config([_SNAPSHOT, _RESTORE])
    )
    await hass.async_block_till_done()
    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()
    assert _reported(issue_registry) is None

    came_or_went, unsubscribe_states = _states_coming_or_going(hass)
    await _reload(hass, automation.DOMAIN, _automation_config([_RESTORE]))
    unsubscribe_states()
    await repair._async_inspect_with_cleanup()
    unsubscribe_cache()

    assert not came_or_went
    assert "scene.before" in (_reported(issue_registry) or "")


async def test_scene_created_after_a_script_reload_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a `scene.create` a script gains in a reload counts right away."""
    hass.states.async_set("light.hall", "on")
    unsubscribe_cache = entity_filtering.async_setup_all_entity_ids_cache_invalidation(
        hass
    )
    assert await async_setup_component(hass, script.DOMAIN, _script_config([]))
    await hass.async_block_till_done()
    repair = ScriptSpookRepair(hass)
    await repair._async_inspect_with_cleanup()

    came_or_went, unsubscribe_states = _states_coming_or_going(hass)
    await _reload(hass, script.DOMAIN, _script_config([_SNAPSHOT, _RESTORE]))
    unsubscribe_states()
    await repair._async_inspect_with_cleanup()
    unsubscribe_cache()

    assert not came_or_went
    assert _script_reported(issue_registry) is None


async def test_scene_no_longer_created_after_a_script_reload_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a `scene.create` a script loses in a reload stops counting."""
    hass.states.async_set("light.hall", "on")
    unsubscribe_cache = entity_filtering.async_setup_all_entity_ids_cache_invalidation(
        hass
    )
    assert await async_setup_component(
        hass, script.DOMAIN, _script_config([_SNAPSHOT, _RESTORE])
    )
    await hass.async_block_till_done()
    repair = ScriptSpookRepair(hass)
    await repair._async_inspect_with_cleanup()
    assert _script_reported(issue_registry) is None

    came_or_went, unsubscribe_states = _states_coming_or_going(hass)
    await _reload(hass, script.DOMAIN, _script_config([_RESTORE]))
    unsubscribe_states()
    await repair._async_inspect_with_cleanup()
    unsubscribe_cache()

    assert not came_or_went
    assert "scene.before" in (_script_reported(issue_registry) or "")


async def test_every_caller_sees_a_scene_created_after_a_reload(
    hass: HomeAssistant,
) -> None:
    """Test the repairs that do not walk automations see the scene too.

    Dashboards, scenes, templates and the rest ask for the known entity IDs,
    and the rename suggestions ask for them per domain. Both are cached, and
    both have to know a scene an automation started creating in a reload.
    """
    hass.states.async_set("light.hall", "on")
    unsubscribe_cache = entity_filtering.async_setup_all_entity_ids_cache_invalidation(
        hass
    )
    assert await async_setup_component(hass, automation.DOMAIN, _automation_config([]))
    await hass.async_block_till_done()
    entity_filtering.async_get_all_entity_ids(hass)
    entity_filtering.async_get_all_entity_ids_by_domain(hass)

    await _reload(hass, automation.DOMAIN, _automation_config([_SNAPSHOT]))
    known_entity_ids = entity_filtering.async_get_all_entity_ids(hass)
    known_by_domain = entity_filtering.async_get_all_entity_ids_by_domain(hass)
    unsubscribe_cache()

    assert "scene.before" in known_entity_ids
    assert "scene.before" in known_by_domain["scene"]


async def test_scenes_read_are_not_kept_past_a_reload(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test what was read from an old configuration goes with it.

    The scenes are read per configuration and kept with the automation they
    were read from. Ten reloads later, only the one configuration still in
    use is remembered.
    """
    owned: WeakKeyDictionary[Any, Any] = WeakKeyDictionary()
    monkeypatch.setattr(configuration_cache, "_READINGS", owned)
    reader = entity_filtering._scene_ids_created_by.__wrapped__  # type: ignore[attr-defined]
    hass.states.async_set("light.hall", "on")
    assert await async_setup_component(
        hass, automation.DOMAIN, _automation_config([_SNAPSHOT])
    )
    await hass.async_block_till_done()

    for round_number in range(10):
        await _reload(
            hass,
            automation.DOMAIN,
            _automation_config([_SNAPSHOT, {"delay": round_number}]),
        )
        entity_filtering.async_get_all_entity_ids(hass)
    gc.collect()

    assert [len(readings.get(reader, {})) for readings in owned.values()] == [1]


async def test_asking_again_reads_nothing_until_a_configuration_changes(
    hass: HomeAssistant,
) -> None:
    """Test the created scenes are read once, however often they are asked for.

    Every issue that is written asks for them. As long as every automation
    and script still has the very same configuration, nothing is read again.
    A reload that changes one makes it read once more, and that is all.
    """
    hass.states.async_set("light.hall", "on")
    assert await async_setup_component(
        hass, automation.DOMAIN, _automation_config([_SNAPSHOT])
    )
    await hass.async_block_till_done()

    with patch.object(
        entity_filtering, "reading_for", wraps=entity_filtering.reading_for
    ) as reading_for:
        first = entity_filtering.async_get_created_scene_ids(hass)
        read_at_first = reading_for.call_count
        again = [entity_filtering.async_get_created_scene_ids(hass) for _ in range(5)]
        read_when_asked_again = reading_for.call_count

        await _reload(
            hass, automation.DOMAIN, _automation_config([_SNAPSHOT, {"delay": 1}])
        )
        after_reload = entity_filtering.async_get_created_scene_ids(hass)
        read_after_reload = reading_for.call_count

    assert first == {"scene.before"}
    assert again == [first] * 5
    assert after_reload == first
    assert (read_at_first, read_when_asked_again, read_after_reload) == (1, 1, 2)
