"""Tests for how the unknown attribute repairs go about a round."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.const import EVENT_CALL_SERVICE, EVENT_STATE_CHANGED
from homeassistant.helpers.entity_component import DATA_INSTANCES

from custom_components.spook import repairs
from custom_components.spook.ectoplasms.script.repairs.unknown_attribute_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "script_unknown_attribute_references_script.haunted"


def _scripts(hass: HomeAssistant, *entities: SimpleNamespace) -> SimpleNamespace:
    """Stand in for the script component, holding these scripts.

    Its `entities` can be swapped out, like a reload does.
    """
    component = SimpleNamespace(entities=list(entities))
    component.get_entity = lambda entity_id: next(
        (entity for entity in component.entities if entity.entity_id == entity_id),
        None,
    )
    hass.data.setdefault(DATA_INSTANCES, {})["script"] = component
    return component


def _script(config: dict[str, Any], entity_id: str = "script.haunted") -> Any:
    """Return a stand-in script with this configuration."""
    return SimpleNamespace(
        entity_id=entity_id,
        name="Haunted",
        unique_id="haunted",
        raw_config=config,
    )


def _following(options: dict[str, Any], **target: Any) -> dict[str, Any]:
    """Return a script waiting on Spook's state trigger, following Brightness."""
    trigger: dict[str, Any] = {
        "trigger": "spook.state_changed",
        "options": {"attribute": "Brightness", **options},
    }
    if target:
        trigger["target"] = target
    return {"sequence": [{"wait_for_trigger": [trigger]}]}


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            _following({"domain": ["light"]}),
            ["light.hall", "light.kitchen"],
            id="picked by domain",
        ),
        pytest.param(
            _following(
                {"domain": ["light"], "exclude_target": {"entity_id": ["light.hall"]}}
            ),
            ["light.kitchen"],
            id="picked by domain, one left out",
        ),
        pytest.param(
            _following(
                {"exclude_target": {"entity_id": ["light.hall"]}},
                entity_id=["light.kitchen", "light.hall"],
            ),
            ["light.kitchen"],
            id="targeted, one left out",
        ),
        pytest.param(
            _following(
                {"exclude_domain": ["switch"]},
                entity_id=["light.kitchen", "switch.hall"],
            ),
            ["light.kitchen"],
            id="targeted, a domain left out",
        ),
    ],
)
async def test_spook_trigger_names_what_it_watches(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
    expected: list[str],
) -> None:
    """Test Spook's own trigger names exactly the entities it would watch.

    Resolved by the trigger itself: its filters pick, its exclusions leave
    out, and nothing else is looked at.
    """
    hass.states.async_set("light.kitchen", "on", {"brightness": 1})
    hass.states.async_set("light.hall", "on", {"brightness": 1})
    hass.states.async_set("switch.hall", "on", {"brightness": 1})
    _scripts(hass, _script(config))

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["attributes"] == "\n".join(
        f"- `Brightness` of `{entity_id}` (did you mean `brightness`?)"
        for entity_id in expected
    )


async def test_findings_follow_the_configuration_they_came_from(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a script reloaded while the round waits is not reported on.

    What was found is about the configuration that was read, and the one
    there now may say something else. The next round looks at that one.
    """
    hass.states.async_set("light.kitchen", "on", {"brightness": 1})
    config = {
        "sequence": [
            {"wait_template": "{{ state_attr('light.kitchen', 'Brightness') }}"}
        ]
    }
    haunted = _script(config)
    _scripts(hass, haunted)
    working_out = repairs.async_unknown_attributes

    async def _reloaded_meanwhile(hass: HomeAssistant, pairs: Any) -> Any:
        found = await working_out(hass, pairs)
        haunted.raw_config = dict(config)
        return found

    monkeypatch.setattr(repairs, "async_unknown_attributes", _reloaded_meanwhile)
    repair = SpookRepair(hass)
    await repair.async_inspect()
    assert async_issue_about(issue_registry, ISSUE) is None

    monkeypatch.setattr(repairs, "async_unknown_attributes", working_out)
    await repair.async_inspect()
    assert async_issue_about(issue_registry, ISSUE)


async def test_findings_stay_with_the_script_they_came_from(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a script replaced while the round goes by is not reported on.

    The round goes by the scripts as they were when it started. A reload
    meanwhile puts a new script in place of the old one, which still holds
    the old configuration, so that alone says nothing.
    """
    hass.states.async_set("light.kitchen", "on", {"brightness": 1})
    haunted = _script(
        {
            "sequence": [
                {"wait_template": "{{ state_attr('light.kitchen', 'Brightness') }}"}
            ]
        }
    )
    component = _scripts(hass, haunted)
    repair = SpookRepair(hass)
    computing = repair._async_compute_unknown_references  # noqa: SLF001

    async def _replaced_meanwhile(entity: Any) -> set[str]:
        component.entities = [_script({"sequence": []})]
        return await computing(entity)

    monkeypatch.setattr(
        repair, "_async_compute_unknown_references", _replaced_meanwhile
    )
    await repair.async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


async def test_reading_every_configuration_yields(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test reading the configurations gives the event loop a turn after each.

    120 scripts: once for each while reading them, and twice more in the base
    round.
    """
    _scripts(
        hass,
        *(_script({"sequence": []}, f"script.spooky_{index}") for index in range(120)),
    )
    sleeps: list[float] = []
    original_sleep = asyncio.sleep

    async def _counting_sleep(delay: float, result: object = None) -> object:
        sleeps.append(delay)
        return await original_sleep(delay, result)

    monkeypatch.setattr(asyncio, "sleep", _counting_sleep)

    await SpookRepair(hass).async_inspect()

    assert sleeps == [0] * 122


async def test_looks_once_a_reload_is_done(hass: HomeAssistant) -> None:
    """Test a reload is looked at once it changed something, not when asked for.

    Asking for a reload changes nothing yet. Once it is done, what changed
    was removed and added back, and that is when to look.
    """
    _scripts(hass)
    repair = SpookRepair(hass)
    await repair.async_activate()
    repair.inspect_debouncer.async_shutdown()

    looks: list[str] = []

    async def _async_call() -> None:
        looks.append("call")

    repair.inspect_debouncer = SimpleNamespace(
        async_call=_async_call,
        async_schedule_call=lambda: looks.append("schedule"),
        async_shutdown=lambda: None,
    )

    hass.bus.async_fire(EVENT_CALL_SERVICE, {"domain": "script", "service": "reload"})
    await hass.async_block_till_done()
    assert not looks

    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {"entity_id": "script.haunted", "old_state": None, "new_state": None},
    )
    await hass.async_block_till_done()
    assert looks == ["schedule"]

    await repair.async_deactivate()
