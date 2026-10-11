"""Tests for the Lovelace removed users repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.util import dt as dt_util

from custom_components.spook.draft_checking import async_check_draft
from custom_components.spook.ectoplasms.lovelace.repairs.unknown_user_references import (
    SpookRepair,
)
import pytest
from tests.repair_helpers import async_issue_about, async_removed_user_id

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE = "lovelace_unknown_user_references_lovelace"


def _dashboard(config: Any) -> SimpleNamespace:
    """Return the default dashboard with this config."""

    async def async_load(*, force: bool) -> Any:
        """Return the same config every time, like a dashboard nobody saved."""
        del force
        return config

    return SimpleNamespace(
        url_path="lovelace", config={"title": "Overview"}, async_load=async_load
    )


def _with_cards(*cards: Any, **view: Any) -> dict[str, Any]:
    """Return a dashboard config with these cards on its second view."""
    return {
        "views": [
            {"path": "home", "cards": []},
            {"path": "kitchen", "cards": list(cards), **view},
        ]
    }


def _only_for(*user_ids: str) -> list[dict[str, Any]]:
    """Return a visibility that shows something to these users only."""
    return [{"condition": "user", "users": list(user_ids)}]


async def _reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, config: Any
) -> str | None:
    """Inspect a dashboard with this config, and return the users reported."""
    repair = SpookRepair(hass)
    repair._dashboards = {"lovelace": _dashboard(config)}  # noqa: SLF001
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    if (issue := async_issue_about(issue_registry, _ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["users"]


async def test_a_removed_user_in_a_visibility_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a card shown only to a removed user is reported, and where."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(
            hass,
            issue_registry,
            _with_cards({"type": "tile", "visibility": _only_for(removed)}),
        )
        == f"- `{removed}`"
    )

    issue = async_issue_about(issue_registry, _ISSUE)
    assert issue
    assert issue.translation_key == "lovelace_unknown_user_references"
    assert issue.translation_placeholders == {
        "users": f"- `{removed}`",
        "dashboard": "Overview",
        "edit": "/lovelace/kitchen?edit=1",
    }
    assert issue.learn_more_url == "https://spook.boo/lovelace#removed-users"


async def test_users_that_exist_are_not_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test only the removed user of a list is reported.

    The system users Home Assistant makes itself, like the one of an add-on,
    are users too.
    """
    removed = await async_removed_user_id(hass)
    person = await hass.auth.async_create_user("Frenck")
    system = await hass.auth.async_create_system_user("Supervisor")

    assert (
        await _reported(
            hass,
            issue_registry,
            _with_cards(
                {"type": "tile", "visibility": _only_for(person.id, removed)},
                {"type": "tile", "visibility": _only_for(system.id)},
            ),
        )
        == f"- `{removed}`"
    )

    assert (
        await _reported(
            hass,
            issue_registry,
            _with_cards({"type": "tile", "visibility": _only_for(person.id)}),
        )
        is None
    )
    assert (
        await _reported(
            hass,
            issue_registry,
            _with_cards({"type": "tile", "visibility": _only_for(system.id)}),
        )
        is None
    )


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(
            {
                "views": [
                    {
                        "type": "sections",
                        "sections": [{"cards": [], "visibility": "USERS"}],
                    }
                ]
            },
            id="section",
        ),
        pytest.param(
            {"views": [{"badges": [{"type": "entity", "visibility": "USERS"}]}]},
            id="badge",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "heading",
                    "badges": [{"type": "entity", "visibility": "USERS"}],
                }
            ),
            id="heading-badge",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "vertical-stack",
                    "cards": [{"type": "tile", "visibility": "USERS"}],
                }
            ),
            id="stacked",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "tile",
                    "visibility": [
                        {"condition": "or", "conditions": "USERS"},
                    ],
                }
            ),
            id="or",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "tile",
                    "visibility": [
                        {
                            "condition": "and",
                            "conditions": [{"condition": "not", "conditions": "USERS"}],
                        },
                    ],
                }
            ),
            id="nested",
        ),
        pytest.param(
            _with_cards(
                {"type": "conditional", "conditions": "USERS", "card": {"type": "tile"}}
            ),
            id="conditional-card",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "entities",
                    "entities": [
                        {
                            "type": "conditional",
                            "conditions": "USERS",
                            "row": {"entity": "light.kitchen"},
                        }
                    ],
                }
            ),
            id="conditional-row",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "picture-elements",
                    "elements": [
                        {"type": "conditional", "conditions": "USERS", "elements": []}
                    ],
                }
            ),
            id="conditional-element",
        ),
        pytest.param(
            _with_cards({"type": "custom:mushroom-card", "visibility": "USERS"}),
            id="custom-card-visibility",
        ),
        pytest.param(
            {"views": [{"path": "secret", "visible": "VISIBLE"}]},
            id="view-visible",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "button",
                    "tap_action": {
                        "action": "toggle",
                        "confirmation": {"exemptions": "VISIBLE"},
                    },
                }
            ),
            id="confirmation",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "entities",
                    "entities": [
                        {
                            "entity": "lock.front_door",
                            "confirmation": {"exemptions": "VISIBLE"},
                        }
                    ],
                }
            ),
            id="row-confirmation",
        ),
    ],
)
async def test_every_place_a_dashboard_names_a_user_is_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, config: Any
) -> None:
    """Test a removed user is found wherever the frontend compares users."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(hass, issue_registry, _filled_in(config, removed))
        == f"- `{removed}`"
    )


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(
            _with_cards(
                {
                    "type": "tile",
                    "visibility": [
                        {"condition": "user", "users": "IDS", "enabled": False}
                    ],
                }
            ),
            id="switched-off",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "tile",
                    "visibility": [
                        {"condition": "user", "users": "IDS", "enabled": "{{ x }}"}
                    ],
                }
            ),
            id="switched-by-a-template",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "custom:button-card",
                    "state": [{"condition": "user", "users": "IDS"}],
                    "confirmation": {"exemptions": "VISIBLE"},
                }
            ),
            id="inside-a-custom-card",
        ),
        pytest.param(
            _with_cards(
                {
                    "type": "button",
                    "tap_action": {
                        "action": "perform-action",
                        "perform_action": "notify.notify",
                        "data": {"confirmation": {"exemptions": "VISIBLE"}},
                    },
                }
            ),
            id="action-data",
        ),
        pytest.param(
            _with_cards({"type": "tile", "visible": "VISIBLE"}),
            id="visible-on-a-card",
        ),
        pytest.param(
            {"views": [{"strategy": {"type": "custom:mine", "visibility": "USERS"}}]},
            id="strategy",
        ),
        pytest.param(
            _with_cards({"type": "tile", "visibility": _only_for("casper")}),
            id="not-a-user-id",
        ),
    ],
)
async def test_what_is_not_a_user_the_frontend_checks_is_not_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, config: Any
) -> None:
    """Test a removed user is left alone where nothing compares it with users.

    A condition switched off, the inside of a custom card, data handed to an
    action, a `visible` anywhere but on a view, a strategy's options, and
    something that was never a user ID.
    """
    removed = await async_removed_user_id(hass)

    assert await _reported(hass, issue_registry, _filled_in(config, removed)) is None


def _filled_in(node: Any, user_id: str) -> Any:
    """Return a config with the markers swapped for the shapes they stand for.

    `USERS` is a user condition, `IDS` a list of users, and `VISIBLE` a list
    of `{user: ...}`, each naming this user.
    """
    markers = {
        "USERS": [{"condition": "user", "users": [user_id]}],
        "IDS": [user_id],
        "VISIBLE": [{"user": user_id}],
    }
    if isinstance(node, str):
        return markers.get(node, node)
    if isinstance(node, list):
        return [_filled_in(item, user_id) for item in node]
    if isinstance(node, dict):
        return {key: _filled_in(value, user_id) for key, value in node.items()}
    return node


async def test_the_edit_link_opens_the_view_naming_the_user(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the issue links to the first view naming a removed user."""
    removed = await async_removed_user_id(hass)

    await _reported(
        hass,
        issue_registry,
        {
            "views": [
                {"path": "home"},
                {"visible": [{"user": removed}]},
                {"path": "attic", "visible": [{"user": removed}]},
            ]
        },
    )

    issue = async_issue_about(issue_registry, _ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["edit"] == "/lovelace/1?edit=1"


async def test_removing_a_user_is_noticed_and_fixing_it_clears_the_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test removing a user raises the issue, and dropping the user clears it."""
    await hass.auth.async_create_user("Owner")
    user = await hass.auth.async_create_user("Casper")
    config = _with_cards({"type": "tile", "visibility": _only_for(user.id)})
    hass.data["lovelace"] = SimpleNamespace(dashboards={"lovelace": _dashboard(config)})

    repair = SpookRepair(hass)
    await repair.async_activate()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert async_issue_about(issue_registry, _ISSUE) is None

    await hass.auth.async_remove_user(user)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert async_issue_about(issue_registry, _ISSUE)

    config["views"][1]["cards"] = []
    hass.bus.async_fire("lovelace_updated", {"url_path": None})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
    await hass.async_block_till_done()
    assert async_issue_about(issue_registry, _ISSUE) is None

    await repair.async_deactivate()


async def test_a_draft_names_the_removed_users(hass: HomeAssistant) -> None:
    """Test a draft card naming a removed user is caught before it is saved."""
    removed = await async_removed_user_id(hass)
    person = await hass.auth.async_create_user("Frenck")

    assert await async_check_draft(
        hass,
        "dashboard",
        {"type": "tile", "visibility": _only_for(person.id, removed)},
    ) == {"users": [removed]}


async def test_a_draft_dashboard_names_the_removed_users_of_its_views(
    hass: HomeAssistant,
) -> None:
    """Test a whole draft dashboard has the users its views are visible to read."""
    removed = await async_removed_user_id(hass)

    assert await async_check_draft(
        hass,
        "dashboard",
        {"views": [{"path": "secret", "visible": [{"user": removed}]}]},
    ) == {"users": [removed]}


async def test_a_draft_view_names_the_removed_users_it_is_visible_to(
    hass: HomeAssistant,
) -> None:
    """Test a single draft view has its own `visible` read, like a saved one."""
    removed = await async_removed_user_id(hass)

    assert await async_check_draft(
        hass,
        "dashboard",
        {"path": "secret", "visible": [{"user": removed}], "cards": []},
    ) == {"users": [removed]}
    assert await async_check_draft(
        hass,
        "dashboard",
        {"type": "sections", "visible": [{"user": removed}], "sections": []},
    ) == {"users": [removed]}


async def test_a_draft_card_has_no_visible_to_read(hass: HomeAssistant) -> None:
    """Test a card on its own is not taken for a view."""
    removed = await async_removed_user_id(hass)

    assert (
        await async_check_draft(
            hass, "dashboard", {"type": "tile", "visible": [{"user": removed}]}
        )
        == {}
    )
