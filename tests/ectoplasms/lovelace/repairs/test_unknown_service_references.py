"""Tests for the Lovelace unknown actions repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED

from custom_components.spook.ectoplasms.lovelace.repairs.unknown_service_references import (
    SpookRepair,
)
import pytest
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


def _dashboard_with_card(card: dict[str, Any]) -> SimpleNamespace:
    """Return a dashboard holding just this card."""

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the dashboard config."""
        del force
        return {"views": [{"path": "home", "cards": [card]}]}

    return SimpleNamespace(
        url_path="lovelace", config={"title": "Overview"}, async_load=async_load
    )


def _picture_elements(*elements: dict[str, Any]) -> dict[str, Any]:
    """Return a picture-elements card holding these elements."""
    return {
        "type": "picture-elements",
        "image": "/local/floorplan.png",
        "elements": list(elements),
    }


@pytest.mark.parametrize(
    "element",
    [
        {
            "type": "service-button",
            "title": "Turn on",
            "service": "script.renamed_away",
            "service_data": {"entity_id": "light.kitchen"},
        },
        {
            "type": "service-button",
            "title": "Turn on",
            "action": "script.renamed_away",
            "data": {"entity_id": "light.kitchen"},
        },
        {
            "type": "action-button",
            "title": "Turn on",
            "action": "script.renamed_away",
        },
        {
            "type": "service-button",
            "title": "Turn on",
            "action": "script.renamed_away",
            "service": "script.known",
        },
        {
            "type": "conditional",
            "conditions": [],
            "elements": [
                {
                    "type": "service-button",
                    "title": "Turn on",
                    "service": "script.renamed_away",
                },
            ],
        },
    ],
    ids=["service", "action", "action-button", "action-over-service", "conditional"],
)
async def test_an_unknown_action_in_a_button_element_creates_an_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    element: dict[str, Any],
) -> None:
    """Test a picture-elements button performing a missing action is reported.

    The element names its action at the top level, under `action` or the
    older `service`, rather than in a tap action, and was never read.
    """
    hass.services.async_register("script", "known", lambda _: None)

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": _dashboard_with_card(_picture_elements(element)),
    }

    await repair.async_inspect()

    issue = async_issue_about(issue_registry, _ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["services"] == "- `script.renamed_away`"


async def test_a_known_action_in_a_button_element_creates_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a picture-elements button performing an existing action is fine."""
    hass.services.async_register("script", "known", lambda _: None)

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": _dashboard_with_card(
            _picture_elements(
                {"type": "service-button", "title": "Go", "service": "script.known"},
                {"type": "action-button", "title": "Go", "action": "script.known"},
                # The frontend runs `action` and never looks at `service`.
                {
                    "type": "service-button",
                    "title": "Go",
                    "action": "script.known",
                    "service": "script.renamed_away",
                },
            )
        ),
    }

    await repair.async_inspect()

    assert async_issue_about(issue_registry, _ISSUE) is None


@pytest.mark.parametrize(
    "card",
    [
        _picture_elements(
            {
                "type": "state-label",
                "entity": "sensor.temperature",
                "service": "script.renamed_away",
            },
        ),
        {
            "type": "custom:some-card",
            "service": "script.renamed_away",
            "action": "script.renamed_away",
        },
    ],
    ids=["other-element", "other-card"],
)
async def test_a_service_key_elsewhere_creates_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    card: dict[str, Any],
) -> None:
    """Test a bare `service` or `action` outside the button element is left alone.

    On anything else the key means whatever that card or element says it
    means, and nothing performs it as an action.
    """
    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": _dashboard_with_card(card),
    }

    await repair.async_inspect()

    assert async_issue_about(issue_registry, _ISSUE) is None
