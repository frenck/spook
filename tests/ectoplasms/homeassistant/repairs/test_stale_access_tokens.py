"""Tests for the stale long-lived access tokens repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.auth.models import (
    TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
    TOKEN_TYPE_NORMAL,
)
from homeassistant.util import dt as dt_util

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs.stale_access_tokens import (
    SpookRepair,
)
from custom_components.spook.repairs import (
    StaleAccessTokenFixFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir
    import pytest

_REPAIR = "stale_access_tokens"


def _issue_id(token_id: str) -> str:
    """Return the registry issue id for a token."""
    return f"{_REPAIR}_{token_id}"


def _token(
    token_id: str,
    token_type: str,
    days_ago: int,
    name: str = "Script",
    *,
    used: bool = True,
) -> SimpleNamespace:
    """Return a fake refresh token.

    With ``used=False`` the token has never been used (``last_used_at`` is
    ``None``), so the repair must fall back to ``created_at``.
    """
    when = dt_util.utcnow() - timedelta(days=days_ago)
    return SimpleNamespace(
        id=token_id,
        token_type=token_type,
        client_name=name,
        created_at=when,
        last_used_at=when if used else None,
    )


def _set_users(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    users: list[SimpleNamespace],
) -> None:
    """Make the repair see the given users."""

    async def _async_get_users() -> list[SimpleNamespace]:
        return users

    monkeypatch.setattr(hass.auth, "async_get_users", _async_get_users)


async def test_stale_token_creates_fixable_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a long-unused long-lived token gets its own fixable issue."""
    user = SimpleNamespace(
        system_generated=False,
        name="Frenck",
        refresh_tokens={
            "a": _token("stale", TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN, 400, "Old"),
            "b": _token("fresh", TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN, 10, "Fresh"),
            "c": _token("normal", TOKEN_TYPE_NORMAL, 400, "Browser"),
        },
    )
    _set_users(hass, monkeypatch, [user])

    await SpookRepair(hass).async_inspect()

    # Only the stale long-lived token gets an issue.
    assert issue_registry.async_get_issue(DOMAIN, _issue_id("fresh")) is None
    assert issue_registry.async_get_issue(DOMAIN, _issue_id("normal")) is None

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id("stale"))
    assert issue
    assert issue.is_fixable
    assert issue.data == {
        "stale_access_token_id": "stale",
        "token": "Old",
        "owner": "Frenck",
        "last_active": issue.translation_placeholders["last_active"],
    }


async def test_system_user_tokens_are_ignored(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test tokens of system-generated users are not reported."""
    user = SimpleNamespace(
        system_generated=True,
        name="Supervisor",
        refresh_tokens={
            "a": _token("sys", TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN, 400, "System"),
        },
    )
    _set_users(hass, monkeypatch, [user])

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id("sys")) is None


async def test_only_fresh_tokens_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test recently used long-lived tokens produce no issue."""
    user = SimpleNamespace(
        system_generated=False,
        name="Frenck",
        refresh_tokens={
            "a": _token("active", TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN, 5, "Active"),
        },
    )
    _set_users(hass, monkeypatch, [user])

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id("active")) is None


async def test_never_used_token_falls_back_to_created_at(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a never-used long-lived token is judged by its creation date."""
    created = dt_util.utcnow() - timedelta(days=400)
    user = SimpleNamespace(
        system_generated=False,
        name="Frenck",
        refresh_tokens={
            "a": _token(
                "never",
                TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
                400,
                "Never used",
                used=False,
            ),
        },
    )
    _set_users(hass, monkeypatch, [user])

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id("never"))
    assert issue
    assert issue.translation_placeholders
    # Last active falls back to the creation date.
    assert issue.translation_placeholders["last_active"] == created.date().isoformat()


async def test_fix_flow_revokes_token(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test confirming the fix flow revokes the token."""
    token = _token("stale", TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN, 400, "Old")
    removed: list[object] = []

    monkeypatch.setattr(
        hass.auth,
        "async_get_refresh_token",
        lambda ref: token if ref == "stale" else None,
    )
    monkeypatch.setattr(
        hass.auth,
        "async_remove_refresh_token",
        removed.append,
    )

    flow = await async_create_fix_flow(
        hass,
        _issue_id("stale"),
        {
            "stale_access_token_id": "stale",
            "token": "Old",
            "owner": "Frenck",
            "last_active": "2025-01-01",
        },
    )
    assert isinstance(flow, StaleAccessTokenFixFlow)
    flow.hass = hass

    # The form is shown first, no token removed yet.
    await flow.async_step_init()
    assert not removed

    # Confirming revokes the token.
    await flow.async_step_confirm({})
    assert removed == [token]


async def test_fix_flow_survives_already_revoked_token(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test confirming a token that is already gone does not blow up."""
    removed: list[object] = []
    monkeypatch.setattr(
        hass.auth,
        "async_get_refresh_token",
        lambda _token_id: None,
    )
    monkeypatch.setattr(
        hass.auth,
        "async_remove_refresh_token",
        removed.append,
    )

    flow = StaleAccessTokenFixFlow("gone", {})
    flow.hass = hass

    await flow.async_step_confirm({})
    assert not removed
