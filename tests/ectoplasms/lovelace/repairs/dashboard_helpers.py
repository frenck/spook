"""Shared helpers for the dashboard attribute and state repair tests."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.util import dt as dt_util

from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


def dashboard(*cards: Any, **view: Any) -> SimpleNamespace:
    """Return a dashboard with these cards on its second view."""
    config = {
        "views": [
            {"path": "home", "cards": []},
            {"path": "kitchen", "cards": list(cards), **view},
        ]
    }

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the same config every time, like a dashboard nobody saved."""
        del force
        return config

    return SimpleNamespace(
        url_path="lovelace", config={"title": "Overview"}, async_load=async_load
    )


async def async_assert_waits_for_the_recorder(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    repair_class: type,
    issue_id: str,
    card: dict[str, Any],
) -> None:
    """Assert a repair looks at nothing until a while after starting.

    A dashboard being saved meanwhile does not hurry it along either.
    """
    hass.data["lovelace"] = SimpleNamespace(dashboards={"lovelace": dashboard(card)})

    repair = repair_class(hass)
    await repair.async_activate()

    hass.bus.async_fire("lovelace_updated", {"url_path": None})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=9))
    await hass.async_block_till_done()
    assert async_issue_about(issue_registry, issue_id) is None

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10, seconds=1))
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10, seconds=5))
    await hass.async_block_till_done()
    assert async_issue_about(issue_registry, issue_id)

    await repair.async_deactivate()
