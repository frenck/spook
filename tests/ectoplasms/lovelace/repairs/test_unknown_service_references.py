"""Tests for the Lovelace unknown actions repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED

from custom_components.spook.ectoplasms.lovelace.repairs.unknown_service_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE = "lovelace_unknown_service_references_lovelace"


def _dashboard_performing(*actions: str) -> SimpleNamespace:
    """Return a dashboard whose second view has a button per action."""

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the dashboard config."""
        del force
        return {
            "views": [
                {"path": "home", "cards": [{"type": "tile"}]},
                {
                    "path": "bedroom",
                    "cards": [
                        {
                            "type": "button",
                            "tap_action": {
                                "action": "perform-action",
                                "perform_action": action,
                            },
                        }
                        for action in actions
                    ],
                },
            ],
        }

    return SimpleNamespace(
        url_path="lovelace", config={"title": "Overview"}, async_load=async_load
    )


async def test_an_unknown_action_creates_an_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a button performing an action that does not exist is reported."""
    hass.services.async_register("script", "known", lambda _: None)

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": _dashboard_performing("script.known", "script.renamed_away"),
    }

    await repair.async_inspect()

    issue = async_issue_about(issue_registry, _ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["services"] == "- `script.renamed_away`"
    assert issue.translation_placeholders["dashboard"] == "Overview"
    assert issue.translation_placeholders["edit"] == "/lovelace/bedroom?edit=1"


async def test_known_actions_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a dashboard performing only existing actions is not reported."""
    hass.services.async_register("script", "known", lambda _: None)

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": _dashboard_performing("script.known"),
    }

    await repair.async_inspect()

    assert async_issue_about(issue_registry, _ISSUE) is None


def test_actions_coming_and_going_are_looked_at() -> None:
    """Test the repair looks again when an action is registered or removed.

    Without it, an integration that registers its actions after Spook first
    looked leaves an issue standing about an action that is there.
    """
    assert {
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
    } <= SpookRepair.inspect_events


async def test_an_action_that_shows_up_late_clears_the_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an integration registering its action later takes the issue away."""
    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": _dashboard_performing("slow_integration.do_it"),
    }

    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, _ISSUE)

    hass.services.async_register("slow_integration", "do_it", lambda _: None)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert async_issue_about(issue_registry, _ISSUE) is None
