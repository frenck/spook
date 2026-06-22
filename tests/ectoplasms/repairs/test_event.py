"""Tests for repairs event entity."""
# pylint: disable=protected-access

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import Event

from custom_components.spook.ectoplasms.repairs.event import (
    RepairsSpookEventEntity,
    RepairsSpookEventEntityDescription,
)

if TYPE_CHECKING:
    import pytest


def _create_entity() -> RepairsSpookEventEntity:
    """Create a repairs event entity."""
    return RepairsSpookEventEntity(
        RepairsSpookEventEntityDescription(
            key="event",
            translation_key="repairs_event",
            entity_id="event.repair",
            event_types=["create", "remove", "update"],
        ),
    )


def test_repairs_event_ignores_event_without_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test repairs events without an action are ignored."""
    entity = _create_entity()
    triggered = False
    scheduled = False

    def _trigger_event(*_: object) -> None:
        nonlocal triggered
        triggered = True

    def _schedule_update() -> None:
        nonlocal scheduled
        scheduled = True

    monkeypatch.setattr(entity, "_trigger_event", _trigger_event)
    monkeypatch.setattr(entity, "async_schedule_update_ha_state", _schedule_update)

    entity._handle_repairs_issue_registry_updated_event(  # noqa: SLF001
        Event("repairs_issue_registry_updated", {"domain": "spook"})
    )

    assert not triggered
    assert not scheduled


def test_repairs_event_copies_event_data_before_popping_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test repairs event handling does not mutate the shared event data."""
    entity = _create_entity()
    calls: list[tuple[str, dict[str, str]]] = []
    scheduled = False

    def _trigger_event(event_type: str, data: dict[str, str]) -> None:
        calls.append((event_type, data))

    def _schedule_update() -> None:
        nonlocal scheduled
        scheduled = True

    monkeypatch.setattr(entity, "_trigger_event", _trigger_event)
    monkeypatch.setattr(entity, "async_schedule_update_ha_state", _schedule_update)
    event = Event(
        "repairs_issue_registry_updated",
        {"action": "create", "domain": "spook"},
    )

    entity._handle_repairs_issue_registry_updated_event(event)  # noqa: SLF001

    assert calls == [("create", {"domain": "spook"})]
    assert scheduled
    assert event.data == {"action": "create", "domain": "spook"}
