"""Tests for the repairs.list service."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from homeassistant.components.repairs import DOMAIN
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.repairs.services import list as list_issues

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

    from tests.common import MockUser

EARLIER = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

# Keyed the way the frontend looks titles up: by the issue's domain, and its
# translation key, or its issue ID when it has none.
TRANSLATIONS = {
    "component.hue.issues.bridge_gone.title": "Bridge {bridge} is gone",
    "component.hue.issues.plural.title": "{count, plural, one {# light} other {# lights}}",
    "component.zwave_js.issues.dead_node.title": "Node {node} is dead",
    "component.zwave_js.issues.no_placeholder.title": "Node {node} is sleeping",
}


@pytest.fixture(autouse=True)
async def _repairs(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Raise a few issues, some older, and register the action."""
    assert await async_setup_component(hass, DOMAIN, {})

    freezer.move_to(EARLIER)
    ir.async_create_issue(
        hass,
        "hue",
        "bridge_gone",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="bridge_gone",
        translation_placeholders={"bridge": "Living room"},
        learn_more_url="https://example.com/hue",
    )
    freezer.tick(timedelta(hours=1))
    ir.async_create_issue(
        hass,
        "zwave_js",
        "dead_node_5",
        is_fixable=False,
        severity=ir.IssueSeverity.CRITICAL,
        translation_key="dead_node",
        translation_placeholders={"node": "5"},
        breaks_in_ha_version="2027.1.0",
    )
    freezer.tick(timedelta(hours=1))
    ir.async_create_issue(
        hass,
        "zwave_js",
        "ignored_one",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="dead_node",
        translation_placeholders={"node": "9"},
    )
    ir.async_ignore_issue(hass, "zwave_js", "ignored_one", ignore=True)

    list_issues.SpookService(hass).async_register()


async def _list(
    hass: HomeAssistant, admin: MockUser, **data: Any
) -> list[dict[str, Any]]:
    """Call the action as an admin, and return the issues it lists."""
    with patch.object(list_issues, "async_get_translations", return_value=TRANSLATIONS):
        response = await hass.services.async_call(
            DOMAIN,
            "list",
            data,
            blocking=True,
            return_response=True,
            context=Context(user_id=admin.id),
        )
    assert response is not None
    return response["issues"]  # type: ignore[return-value]


async def test_lists_the_open_issues_newest_first(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Ignored issues stay out, like on the Repairs dashboard."""
    issues = await _list(hass, hass_admin_user)

    assert issues == [
        {
            "domain": "zwave_js",
            "issue_id": "dead_node_5",
            "title": "Node 5 is dead",
            "severity": "critical",
            "created": (EARLIER + timedelta(hours=1)).isoformat(),
            "is_fixable": False,
            "learn_more_url": None,
            "breaks_in_ha_version": "2027.1.0",
            "ignored": False,
        },
        {
            "domain": "hue",
            "issue_id": "bridge_gone",
            "title": "Bridge Living room is gone",
            "severity": "error",
            "created": EARLIER.isoformat(),
            "is_fixable": True,
            "learn_more_url": "https://example.com/hue",
            "breaks_in_ha_version": None,
            "ignored": False,
        },
    ]


async def test_includes_ignored_issues_when_asked(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Asked for, the ignored ones come along, and say that they are."""
    issues = await _list(hass, hass_admin_user, include_ignored=True)

    assert [(issue["issue_id"], issue["ignored"]) for issue in issues] == [
        ("ignored_one", True),
        ("dead_node_5", False),
        ("bridge_gone", False),
    ]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"domain": "hue"}, ["bridge_gone"]),
        ({"domain": ["hue", "zwave_js"]}, ["dead_node_5", "bridge_gone"]),
        ({"severity": "critical"}, ["dead_node_5"]),
        ({"domain": "hue", "severity": "critical"}, []),
    ],
)
async def test_filters_by_domain_and_severity(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    data: dict[str, Any],
    expected: list[str],
) -> None:
    """Both filters take one or a list, and both have to match."""
    issues = await _list(hass, hass_admin_user, **data)

    assert [issue["issue_id"] for issue in issues] == expected


async def test_an_issue_no_longer_raised_is_left_out(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """The registry keeps some issues around after they are gone."""
    registry = ir.async_get(hass)
    key = ("hue", "bridge_gone")
    registry.issues[key] = dataclasses.replace(registry.issues[key], active=False)

    issues = await _list(hass, hass_admin_user, include_ignored=True)

    assert "bridge_gone" not in [issue["issue_id"] for issue in issues]


@pytest.mark.parametrize(
    ("translation_key", "placeholders", "title"),
    [
        # Nothing to look up: the issue ID, like the dashboard falls back to.
        ("not_translated", {}, "no_title"),
        # A placeholder without a value stays as written.
        ("no_placeholder", {}, "Node {node} is sleeping"),
        # Braces that are not a placeholder: the text as written.
        ("plural", {"count": "2"}, "{count, plural, one {# light} other {# lights}}"),
    ],
)
async def test_a_title_that_cannot_be_filled_in_still_reads(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    translation_key: str,
    placeholders: dict[str, str],
    title: str,
) -> None:
    """A title that cannot be filled in cleanly is still something to show."""
    domain = "hue" if translation_key == "plural" else "zwave_js"
    ir.async_create_issue(
        hass,
        domain,
        "no_title",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )

    issues = await _list(hass, hass_admin_user)

    assert next(i["title"] for i in issues if i["issue_id"] == "no_title") == title


async def test_only_an_admin_can_list(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
) -> None:
    """Like the Repairs dashboard itself: titles say a lot about a setup."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "list",
            {},
            blocking=True,
            return_response=True,
            context=Context(user_id=hass_read_only_user.id),
        )
