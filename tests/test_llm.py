"""Tests for Spook's tools for assistants."""

# pylint: disable=wrong-import-order,redefined-outer-name
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from homeassistant.core import Context, ServiceCall
from homeassistant.helpers import (
    entity_registry as er,
    issue_registry as ir,
    label_registry as lr,
)
from homeassistant.helpers.llm import LLMContext, ToolInput
from homeassistant.setup import async_setup_component

from custom_components.spook import draft_checking, llm as spook_llm
from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs.unused_labels import (
    SpookRepair as UnusedLabelsRepair,
)
import pytest

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.llm import Tool, ToolResult

# Comfortably past the unused label repair's grace period.
_AGED = timedelta(days=2)

# The unused label and the automation, in the tests that raise both.
_BOTH = 2

_AUTOMATION_ISSUE = "automation_unknown_entity_references_automation.wake_up_1a2b3c4d"


def _context(user: MockUser | None, language: str | None = "en") -> LLMContext:
    """Return the context a conversation agent hands a tool."""
    return LLMContext(
        platform="test",
        context=None if user is None else Context(user_id=user.id),
        language=language,
        assistant="conversation",
        device_id=None,
    )


def _tools(hass: HomeAssistant) -> dict[str, Tool]:
    """Return Spook's tools for the admin API, by name."""
    offered = spook_llm.async_get_tools(
        hass, _context(None), spook_llm.LLM_API_HOME_ASSISTANT
    )
    assert offered is not None
    return {tool.name: tool for tool in offered.tools}


async def _call(
    hass: HomeAssistant,
    name: str,
    user: MockUser | None,
    language: str | None = "en",
    **tool_args: Any,
) -> ToolResult:
    """Call one of Spook's tools the way Home Assistant would."""
    return await _tools(hass)[name].async_call(
        hass, ToolInput(tool_name=name, tool_args=tool_args), _context(user, language)
    )


@pytest.fixture
async def unused_label(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> lr.LabelEntry:
    """Return a label that a real inspection reported as unused."""
    label = lr.async_get(hass).async_create("Holiday")
    freezer.tick(_AGED)
    await UnusedLabelsRepair(hass).async_inspect()
    return label


@pytest.fixture
def automation_issue(hass: HomeAssistant) -> None:
    """Raise an issue shaped like the automation entity reference repair's."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _AUTOMATION_ISSUE,
        is_fixable=False,
        issue_domain="automation",
        learn_more_url="https://spook.boo/automation",
        severity=ir.IssueSeverity.WARNING,
        translation_key="automation_unknown_entity_references",
        translation_placeholders={
            "automation": "Wake up",
            "entity_id": "automation.wake_up",
            "edit": "/config/automation/edit/wake_up",
            "entities": "- `light.bedrom` (did you mean `light.bedroom`?)",
        },
    )


@pytest.fixture
async def repairs(hass: HomeAssistant) -> None:
    """Set up Home Assistant's repairs, with Spook's fix flows in reach."""
    assert await async_setup_component(hass, "repairs", {})
    hass.config.components.add(DOMAIN)


def test_tools_only_for_the_admin_api(hass: HomeAssistant) -> None:
    """Test Assist gets nothing, and the admin API gets every tool."""
    assert spook_llm.async_get_tools(hass, _context(None), "assist") is None

    offered = spook_llm.async_get_tools(
        hass, _context(None), spook_llm.LLM_API_HOME_ASSISTANT
    )
    assert offered is not None
    assert offered.prompt
    assert "spook__find_usages" in offered.prompt
    assert "spook__list_features" in offered.prompt


def test_no_tools_where_core_cannot_hold_them(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test a Home Assistant without the tool parts gets nothing, quietly.

    Home Assistant 2026.8 and 2026.9 load this platform, but have neither the
    tool results nor the annotations the tools are made of.
    """
    monkeypatch.setattr(spook_llm, "async_get_spook_tools", None)

    assert (
        spook_llm.async_get_tools(
            hass, _context(None), spook_llm.LLM_API_HOME_ASSISTANT
        )
        is None
    )


def test_every_tool_is_prefixed_and_tagged(hass: HomeAssistant) -> None:
    """Test core's requirements hold for every tool, and the annotations tell."""
    tools = _tools(hass)

    assert set(tools) == {
        "spook__overview",
        "spook__list_ghosts",
        "spook__explain_ghost",
        "spook__find_usages",
        "spook__check_references",
        "spook__list_features",
        "spook__ignore_ghost",
        "spook__unignore_ghost",
        "spook__fix_ghost",
    }
    for tool in tools.values():
        assert tool.name.startswith(f"{DOMAIN}__")
        assert tool.integration == DOMAIN
        assert not tool.annotations.open_world

    writers = {name for name, tool in tools.items() if not tool.annotations.read_only}
    assert writers == {
        "spook__ignore_ghost",
        "spook__unignore_ghost",
        "spook__fix_ghost",
    }
    assert tools["spook__fix_ghost"].annotations.destructive
    assert not tools["spook__fix_ghost"].annotations.idempotent
    assert not tools["spook__ignore_ghost"].annotations.destructive


@pytest.mark.usefixtures("automation_issue")
async def test_list_ghosts(
    hass: HomeAssistant, hass_admin_user: MockUser, unused_label: lr.LabelEntry
) -> None:
    """Test the open issues are listed, rendered, and filtered by kind."""
    result = await _call(hass, "spook__list_ghosts", hass_admin_user)

    assert not result.error
    assert result.data["total"] == _BOTH
    ghosts = {ghost["issue_id"]: ghost for ghost in result.data["ghosts"]}
    label_ghost = ghosts[f"unused_labels_{unused_label.label_id}"]
    assert label_ghost["kind"] == "unused_labels"
    assert label_ghost["title"] == "Unused label: Holiday"
    assert label_ghost["is_fixable"] is True
    assert label_ghost["ignored"] is False
    assert label_ghost["severity"] == "warning"
    assert label_ghost["learn_more_url"]
    assert ghosts[_AUTOMATION_ISSUE]["title"] == "Unknown entities used in: Wake up"

    result = await _call(
        hass, "spook__list_ghosts", hass_admin_user, kind="unused_labels"
    )
    assert [ghost["kind"] for ghost in result.data["ghosts"]] == ["unused_labels"]

    result = await _call(hass, "spook__list_ghosts", hass_admin_user, limit=1)
    assert result.data["total"] == _BOTH
    assert len(result.data["ghosts"]) == 1


@pytest.mark.usefixtures("automation_issue")
async def test_list_ghosts_leaves_ignored_out_unless_asked(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test an ignored issue only shows when asked for."""
    ir.async_ignore_issue(hass, DOMAIN, _AUTOMATION_ISSUE, ignore=True)

    result = await _call(hass, "spook__list_ghosts", hass_admin_user)
    assert result.data["total"] == 0

    result = await _call(
        hass, "spook__list_ghosts", hass_admin_user, include_ignored=True
    )
    assert result.data["ghosts"][0]["ignored"] is True


async def test_titles_follow_the_conversation_language(
    hass: HomeAssistant, hass_admin_user: MockUser, unused_label: lr.LabelEntry
) -> None:
    """Test Dutch is answered in Dutch, and an unknown language in English."""
    issue_id = f"unused_labels_{unused_label.label_id}"

    result = await _call(
        hass, "spook__explain_ghost", hass_admin_user, "nl", issue_id=issue_id
    )
    assert result.data["title"] == "Ongebruikt label: Holiday"
    assert {"option": "remove", "label": "Verwijder dit ongebruikte label"} in (
        result.data["fix_options"]
    )

    result = await _call(
        hass, "spook__explain_ghost", hass_admin_user, "xx", issue_id=issue_id
    )
    assert result.data["title"] == "Unused label: Holiday"

    # Any language means the house's own.
    result = await _call(
        hass, "spook__explain_ghost", hass_admin_user, "*", issue_id=issue_id
    )
    assert result.data["title"] == "Unused label: Holiday"

    # A regional code is still its language.
    result = await _call(
        hass, "spook__explain_ghost", hass_admin_user, "nl-NL", issue_id=issue_id
    )
    assert result.data["title"] == "Ongebruikt label: Holiday"


async def test_explain_ghost(
    hass: HomeAssistant, hass_admin_user: MockUser, unused_label: lr.LabelEntry
) -> None:
    """Test a fixable issue is explained with its description and options."""
    result = await _call(
        hass,
        "spook__explain_ghost",
        hass_admin_user,
        issue_id=f"unused_labels_{unused_label.label_id}",
    )

    assert not result.error
    assert "The label Holiday is not applied" in result.data["description"]
    assert {option["option"] for option in result.data["fix_options"]} == {
        "remove",
        "ignore",
        "manage",
    }
    assert result.data["placeholders"] == {"label": "Holiday"}


@pytest.mark.usefixtures("automation_issue")
async def test_explain_ghost_without_a_fix(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test a plain issue brings its description and Spook's suggestions."""
    result = await _call(
        hass, "spook__explain_ghost", hass_admin_user, issue_id=_AUTOMATION_ISSUE
    )

    assert result.data["fix_options"] == []
    assert "did you mean `light.bedroom`?" in result.data["description"]
    assert "[Wake up](/config/automation/edit/wake_up)" in result.data["description"]
    assert result.data["placeholders"]["entity_id"] == "automation.wake_up"


async def test_unknown_issue_is_an_error(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test every tool that takes an issue refuses one that is not there."""
    for name in (
        "spook__explain_ghost",
        "spook__ignore_ghost",
        "spook__unignore_ghost",
    ):
        result = await _call(hass, name, hass_admin_user, issue_id="not_a_thing")
        assert result.error
        assert "not_a_thing" in result.data["error"]

    result = await _call(
        hass, "spook__fix_ghost", hass_admin_user, issue_id="nope", option="remove"
    )
    assert result.error


@pytest.mark.usefixtures("automation_issue")
async def test_non_admin_is_refused(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Test a user who is not an administrator gets nothing at all."""
    for name, args in (
        ("spook__list_ghosts", {}),
        ("spook__overview", {}),
        ("spook__ignore_ghost", {"issue_id": _AUTOMATION_ISSUE}),
    ):
        result = await _call(hass, name, hass_read_only_user, **args)
        assert result.error
        assert "administrators" in result.data["error"]

    issue = ir.async_get(hass).async_get_issue(DOMAIN, _AUTOMATION_ISSUE)
    assert issue is not None
    assert issue.dismissed_version is None


@pytest.mark.usefixtures("automation_issue")
async def test_writing_needs_a_user(hass: HomeAssistant) -> None:
    """Test a change without a user is refused, and reading is not."""
    result = await _call(hass, "spook__ignore_ghost", None, issue_id=_AUTOMATION_ISSUE)
    assert result.error
    assert "no user" in result.data["error"]

    result = await _call(
        hass, "spook__fix_ghost", None, issue_id=_AUTOMATION_ISSUE, option="remove"
    )
    assert result.error

    result = await _call(hass, "spook__list_ghosts", None)
    assert not result.error


@pytest.mark.usefixtures("automation_issue")
async def test_ignore_and_unignore(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test ignoring an issue sticks, and taking it back does too."""
    registry = ir.async_get(hass)

    result = await _call(
        hass, "spook__ignore_ghost", hass_admin_user, issue_id=_AUTOMATION_ISSUE
    )
    assert result.data == {"issue_id": _AUTOMATION_ISSUE, "ignored": True}
    issue = registry.async_get_issue(DOMAIN, _AUTOMATION_ISSUE)
    assert issue is not None
    assert issue.dismissed_version is not None

    result = await _call(
        hass, "spook__unignore_ghost", hass_admin_user, issue_id=_AUTOMATION_ISSUE
    )
    assert result.data == {"issue_id": _AUTOMATION_ISSUE, "ignored": False}
    issue = registry.async_get_issue(DOMAIN, _AUTOMATION_ISSUE)
    assert issue is not None
    assert issue.dismissed_version is None


@pytest.mark.usefixtures("repairs")
async def test_fix_ghost_removes_the_label(
    hass: HomeAssistant, hass_admin_user: MockUser, unused_label: lr.LabelEntry
) -> None:
    """Test the remove option runs Spook's real fix flow and closes the issue."""
    issue_id = f"unused_labels_{unused_label.label_id}"

    result = await _call(
        hass, "spook__fix_ghost", hass_admin_user, issue_id=issue_id, option="remove"
    )

    assert result.data == {"issue_id": issue_id, "outcome": "fixed"}
    assert lr.async_get(hass).async_get_label(unused_label.label_id) is None
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.usefixtures("repairs")
async def test_fix_ghost_reports_an_abort_in_words(
    hass: HomeAssistant, hass_admin_user: MockUser, unused_label: lr.LabelEntry
) -> None:
    """Test an option that ends in an abort says why, the way the dialog does."""
    issue_id = f"unused_labels_{unused_label.label_id}"

    result = await _call(
        hass, "spook__fix_ghost", hass_admin_user, issue_id=issue_id, option="ignore"
    )

    assert result.data["outcome"] == "aborted"
    assert result.data["reason"] == "issue_ignored"
    assert result.data["message"] == (
        "Spook will keep quiet about this label from now on."
    )
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.dismissed_version is not None


@pytest.mark.usefixtures("repairs")
async def test_fix_ghost_refuses_what_the_flow_does_not_offer(
    hass: HomeAssistant, hass_admin_user: MockUser, unused_label: lr.LabelEntry
) -> None:
    """Test an option outside the menu is refused, and nothing is left running."""
    issue_id = f"unused_labels_{unused_label.label_id}"

    result = await _call(
        hass, "spook__fix_ghost", hass_admin_user, issue_id=issue_id, option="burn_it"
    )

    assert result.error
    assert "remove" in result.data["error"]
    assert lr.async_get(hass).async_get_label(unused_label.label_id) is not None
    assert not hass.data["repairs"]["flow_manager"].async_progress()


@pytest.mark.usefixtures("repairs")
async def test_fix_ghost_leaves_a_form_to_a_person(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test a fix that wants a form filled in is handed back, and abandoned."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "restart_required",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="restart_required",
    )

    result = await _call(
        hass,
        "spook__fix_ghost",
        hass_admin_user,
        issue_id="restart_required",
        option="confirm_restart",
    )

    assert result.error
    assert "Repairs dashboard" in result.data["error"]
    assert not hass.data["repairs"]["flow_manager"].async_progress()


@pytest.mark.usefixtures("automation_issue")
async def test_fix_ghost_refuses_an_issue_without_a_fix(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test an issue that is not fixable is refused before anything starts."""
    result = await _call(
        hass,
        "spook__fix_ghost",
        hass_admin_user,
        issue_id=_AUTOMATION_ISSUE,
        option="remove",
    )

    assert result.error
    assert "no fix" in result.data["error"]


class _Dashboard:  # pylint: disable=too-few-public-methods
    """A storage dashboard, as far as Spook reads one."""

    def __init__(self, url_path: str, config: dict[str, Any]) -> None:
        """Hold the dashboard's configuration."""
        self.url_path = url_path
        self.config = {"title": "Home"}
        self._config = config

    async def async_load(self, **_: bool) -> dict[str, Any]:
        """Return the configuration, forced or not."""
        return self._config


async def test_find_usages(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test an entity is found in an automation, a template, and a dashboard."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "wake_up",
                    "alias": "Wake up",
                    "triggers": [{"trigger": "event", "event_type": "go"}],
                    "actions": [
                        {
                            "action": "light.turn_on",
                            "target": {"entity_id": "light.bedroom"},
                        }
                    ],
                },
                {
                    "id": "report",
                    "alias": "Report",
                    "triggers": [{"trigger": "event", "event_type": "go"}],
                    "actions": [
                        {
                            "action": "notify.notify",
                            "data": {
                                "message": "{{ states('light.bedroom') }}",
                            },
                        }
                    ],
                },
                {
                    "id": "unrelated",
                    "alias": "Unrelated",
                    "triggers": [{"trigger": "event", "event_type": "go"}],
                    "actions": [
                        {
                            "action": "light.turn_on",
                            "target": {"entity_id": "light.kitchen"},
                        }
                    ],
                },
            ]
        },
    )
    hass.data["lovelace"] = SimpleNamespace(
        dashboards={
            "lovelace": _Dashboard(
                "lovelace",
                {
                    "views": [
                        {"path": "start", "cards": []},
                        {
                            "path": "upstairs",
                            "cards": [{"type": "light", "entity": "light.bedroom"}],
                        },
                    ]
                },
            )
        }
    )

    result = await _call(
        hass, "spook__find_usages", hass_admin_user, reference=" Light.Bedroom "
    )

    assert not result.error
    assert result.data["reference"] == "light.bedroom"
    assert result.data["searched_as"] == ["entity", "action"]
    found = {(usage["kind"], usage["id"]) for usage in result.data["usages"]}
    assert found == {
        ("automation", "automation.wake_up"),
        ("automation", "automation.report"),
        ("dashboard", "lovelace"),
    }
    by_id = {usage["id"]: usage for usage in result.data["usages"]}
    assert by_id["automation.wake_up"]["edit_url"] == "/config/automation/edit/wake_up"
    assert by_id["automation.wake_up"]["name"] == "Wake up"
    assert by_id["lovelace"]["edit_url"] == "/lovelace/upstairs?edit=1"
    assert by_id["lovelace"]["matched_as"] == "entity"


async def test_find_usages_of_an_action(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test an action is found only where it is performed, when asked for one."""
    hass.services.async_register("notify", "notify", lambda _call: None)
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "say_hi": {
                    "alias": "Say hi",
                    "sequence": [
                        {"action": "notify.notify", "data": {"message": "Hi"}}
                    ],
                }
            }
        },
    )
    hass.data["lovelace"] = SimpleNamespace(dashboards={})

    result = await _call(
        hass,
        "spook__find_usages",
        hass_admin_user,
        reference="notify.notify",
        kind="action",
    )

    assert result.data["searched_as"] == ["action"]
    assert result.data["usages"] == [
        {
            "kind": "script",
            "id": "script.say_hi",
            "name": "Say hi",
            "matched_as": "action",
            "edit_url": "/config/script/edit/say_hi",
        }
    ]


async def test_check_references_finds_the_ghosts_in_a_draft(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a draft automation is read the way the repairs read a saved one."""
    entity_registry.async_get_or_create(
        "light", "hue", "bedroom", suggested_object_id="bedroom"
    )
    hass.services.async_register("light", "turn_on", lambda _call: None)

    result = await _call(
        hass,
        "spook__check_references",
        hass_admin_user,
        kind="automation",
        config={
            "alias": "Draft",
            "triggers": [{"trigger": "state", "entity_id": "binary_sensor.door"}],
            "actions": [
                {"action": "light.turn_on", "target": {"entity_id": "light.bedrom"}},
                {"action": "light.turn_onn", "target": {"area_id": "attic"}},
            ],
        },
    )

    assert not result.error
    assert result.data["clean"] is False
    unknown = result.data["unknown"]
    assert {"entity_id": "light.bedrom", "did_you_mean": "light.bedroom"} in (
        unknown["entities"]
    )
    assert {"entity_id": "binary_sensor.door"} in unknown["entities"]
    assert unknown["services"] == ["light.turn_onn"]
    assert unknown["areas"] == ["attic"]


async def test_check_references_on_a_clean_draft(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a draft that only names what exists comes back clean."""
    entity_registry.async_get_or_create(
        "light", "hue", "bedroom", suggested_object_id="bedroom"
    )
    hass.services.async_register("light", "turn_on", lambda _call: None)

    result = await _call(
        hass,
        "spook__check_references",
        hass_admin_user,
        kind="script",
        config={
            "sequence": [
                {"action": "light.turn_on", "target": {"entity_id": "light.bedroom"}}
            ]
        },
    )

    assert result.data == {"clean": True, "unknown": {}}


async def test_check_references_on_scenes_and_cards(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test a scene and a single dashboard card are checked too."""
    result = await _call(
        hass,
        "spook__check_references",
        hass_admin_user,
        kind="scene",
        config={"name": "Movie", "entities": {"light.cinema": "off"}},
    )
    assert result.data["unknown"] == {"entities": [{"entity_id": "light.cinema"}]}

    result = await _call(
        hass,
        "spook__check_references",
        hass_admin_user,
        kind="dashboard",
        config={
            "type": "button",
            "entity": "switch.ghost",
            "tap_action": {"action": "perform-action", "perform_action": "boo.scare"},
        },
    )
    assert result.data["unknown"] == {
        "entities": [{"entity_id": "switch.ghost"}],
        "services": ["boo.scare"],
    }


async def test_check_references_refuses_what_it_cannot_read(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test a draft that is not what it says it is gets an error, not a pass."""
    result = await _call(
        hass,
        "spook__check_references",
        hass_admin_user,
        kind="script",
        config={"sequence": [{"delay": "not a duration at all"}]},
    )
    assert result.error
    assert "do not validate" in result.data["error"]

    result = await _call(
        hass,
        "spook__check_references",
        hass_admin_user,
        kind="scene",
        config={"entities": ["light.cinema"]},
    )
    assert result.error


@pytest.mark.usefixtures("automation_issue")
async def test_overview(
    hass: HomeAssistant, hass_admin_user: MockUser, unused_label: lr.LabelEntry
) -> None:
    """Test the overview counts per kind, ignored apart, oldest first."""
    ir.async_ignore_issue(
        hass, DOMAIN, f"unused_labels_{unused_label.label_id}", ignore=True
    )

    result = await _call(hass, "spook__overview", hass_admin_user)

    assert result.data["total"] == _BOTH
    assert result.data["open"] == 1
    assert result.data["ignored"] == 1
    assert result.data["kinds"]["unused_labels"] == {
        "example_title": "Unused label: Holiday",
        "open": 0,
        "ignored": 1,
    }
    assert result.data["kinds"]["automation_unknown_entity_references"]["open"] == 1
    assert [ghost["issue_id"] for ghost in result.data["oldest_open"]] == [
        _AUTOMATION_ISSUE
    ]


async def test_list_features(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test Spook's triggers, conditions and registered actions are listed."""

    def _boo(_call: ServiceCall) -> None:
        """Stand in for Spook's own action."""

    hass.services.async_register(DOMAIN, "boo", _boo)
    hass.services.async_register("input_select", "random", _boo)

    result = await _call(hass, "spook__list_features", hass_admin_user, "nl")

    triggers = {trigger["name"]: trigger for trigger in result.data["triggers"]}
    assert triggers["spook.cron"]["title"] == "Cron-schema"
    assert triggers["spook.cron"]["description"].startswith("Wordt geactiveerd")
    assert "spook.is_available" in {
        condition["name"] for condition in result.data["conditions"]
    }
    actions = {action["name"]: action for action in result.data["actions"]}
    assert actions["spook.boo"]["title"] == "Boe!"
    assert "input_select.random" in actions
    # Not registered here, so not something an automation could use.
    assert "group.add_members" not in actions

    result = await _call(hass, "spook__list_features", hass_admin_user, kind="actions")
    assert set(result.data) == {"actions"}


async def test_find_usages_in_scenes_and_helpers(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test scenes, helpers by registry ID, and template helpers are searched."""
    bedroom = entity_registry.async_get_or_create(
        "sensor", "hue", "bedroom", suggested_object_id="bedroom"
    )
    MockConfigEntry(
        domain="derivative", title="Bedroom change", options={"source": bedroom.id}
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="template",
        title="Bedroom in words",
        options={"state": "{{ states('sensor.bedroom') }} degrees"},
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="template", title="Unrelated", options={"state": "{{ 1 }}"}
    ).add_to_hass(hass)
    hass.data["homeassistant_scene"] = SimpleNamespace(
        entities={
            "scene.night": SimpleNamespace(
                entity_id="scene.night",
                name="Night",
                unique_id="night",
                scene_config=SimpleNamespace(states={"sensor.bedroom": None}),
            )
        }
    )
    hass.data["lovelace"] = SimpleNamespace(dashboards={})

    result = await _call(
        hass, "spook__find_usages", hass_admin_user, reference="sensor.bedroom"
    )

    assert {(usage["kind"], usage["name"]) for usage in result.data["usages"]} == {
        ("scene", "Night"),
        ("helper", "Bedroom change"),
        ("template", "Bedroom in words"),
    }
    by_kind = {usage["kind"]: usage for usage in result.data["usages"]}
    assert by_kind["scene"]["edit_url"] == "/config/scene/edit/night"
    assert "edit_url" not in by_kind["helper"]


@pytest.mark.parametrize("domain", ["automation", "script"])
def test_drafts_are_checked_by_every_unknown_reference_repair(domain: str) -> None:
    """Test a new automation or script repair is not left out of draft checks.

    The repairs are listed by hand, so one added later has to be added there
    too, or a draft that passes still gets that repair the moment it is saved.
    """
    repairs_path = Path(spook_llm.__file__).parent / "ectoplasms" / domain / "repairs"
    on_disk = {path.stem for path in repairs_path.glob("unknown_*_references.py")}

    listed = {
        module.__name__.rsplit(".", 1)[1]
        for module in draft_checking.DRAFT_REPAIRS[domain]
    }

    assert listed == on_disk
