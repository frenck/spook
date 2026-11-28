"""Tests for the doors to Spook's tools, the prompt, and the front's budget."""

# pylint: disable=wrong-import-order,redefined-outer-name
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.helpers.llm import (
    LLMContext,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.setup import async_setup_component

from custom_components.spook import llm as spook_llm, llm_tools
from custom_components.spook.const import DOMAIN
import probatio
import pytest

if TYPE_CHECKING:
    from pytest_homeassistant.common import MockUser

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.llm import Tool

# What the stubs below write down when they run, so a test can tell they did
# not.
_RUNS = "spook_test_door_runs"

_DOORS = {"spook__read", "spook__change"}

# What a client receives in the front, in characters: every tool in the front,
# both doors, and the longest prompt. A small local model carries all of that
# on every request, before the conversation even starts. Growing it is a
# decision, never an accident: a new tool goes behind a door unless it has to
# be in the front.
_FRONT_BUDGET = 7_500


def _context(user: MockUser | None) -> LLMContext:
    """Return the context a conversation agent hands a tool."""
    return LLMContext(
        platform="test",
        context=None if user is None else Context(user_id=user.id),
        language="en",
        assistant="conversation",
        device_id=None,
    )


def _offered(hass: HomeAssistant) -> llm_tools.LLMTools:
    """Return what Spook hands the admin API."""
    offered = spook_llm.async_get_tools(
        hass, _context(None), spook_llm.LLM_API_HOME_ASSISTANT
    )
    assert offered is not None
    return offered


def _tools(hass: HomeAssistant) -> dict[str, Tool]:
    """Return Spook's tools for the admin API, by name."""
    return {tool.name: tool for tool in _offered(hass).tools}


async def _call(
    hass: HomeAssistant, name: str, user: MockUser | None, **tool_args: Any
) -> ToolResult:
    """Call one of Spook's tools the way Home Assistant would."""
    return await _tools(hass)[name].async_call(
        hass, ToolInput(tool_name=name, tool_args=tool_args), _context(user)
    )


def _runs(hass: HomeAssistant) -> list[tuple[str, dict[str, Any]]]:
    """Return what the stub tools ran with, in order."""
    return hass.data.get(_RUNS, [])


# pylint: disable-next=too-few-public-methods
class _StubTool(llm_tools.AbstractSpookTool):
    """A tool behind a door, that writes down what it ran with."""

    domain = DOMAIN

    async def _async_run(
        self,
        hass: HomeAssistant,
        args: dict[str, Any],
        llm_context: LLMContext,  # noqa: ARG002
    ) -> ToolResult:
        """Write the arguments down, and hand them back."""
        hass.data.setdefault(_RUNS, []).append((self.name, args))
        return ToolResult(data={"ran": self.name, "args": args})


# pylint: disable-next=too-few-public-methods
class _ReadingTool(_StubTool):
    """A tool that only reads."""

    name = "spook__stub_reading"
    title = "Read a stub"
    description = "Reads a stub. Nothing more to it than that."
    annotations = llm_tools.READ_ONLY
    parameters = probatio.Schema(
        {
            probatio.Required("what", description="What to read."): str,
            probatio.Optional("count", default=1): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            ),
        }
    )


# pylint: disable-next=too-few-public-methods
class _ChangingTool(_StubTool):
    """A tool that changes something."""

    name = "spook__stub_changing"
    title = "Change a stub"
    description = "Changes a stub. It does not, really."
    annotations = ToolAnnotations(
        read_only=False, destructive=False, idempotent=True, open_world=False
    )


# pylint: disable-next=too-few-public-methods
class _FarAwayTool(_StubTool):
    """A tool that only reads, about an integration that is not loaded here."""

    domain = "not_loaded_here"
    name = "spook__stub_far_away"
    description = "Reads something of an integration that is not set up."
    annotations = llm_tools.READ_ONLY


@pytest.fixture(autouse=True)
async def spook_tools(hass: HomeAssistant) -> None:
    """Find Spook's tools, the way setting Spook up does."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "repairs", {})
    hass.config.components.add(DOMAIN)
    await llm_tools.async_setup_spook_tools(hass)


def _add(hass: HomeAssistant, *tools: type[llm_tools.AbstractSpookTool]) -> None:
    """Put tools next to the ones Spook found, in the order Spook keeps them."""
    found = hass.data[llm_tools.DATA_TOOLS]
    found.extend(tools)
    found.sort(key=lambda tool: tool.name)


def test_no_door_while_nothing_is_behind_it(hass: HomeAssistant) -> None:
    """Test the doors stay out of sight while every tool is in the front."""
    tools = _tools(hass)

    assert not set(tools) & _DOORS
    assert tools
    assert all(tool.in_front for tool in tools.values())


def test_a_door_appears_once_something_is_behind_it(hass: HomeAssistant) -> None:
    """Test a door is handed out for its own kind only, and not what it opens."""
    _add(hass, _FarAwayTool)
    assert not set(_tools(hass)) & _DOORS

    _add(hass, _ReadingTool)
    tools = _tools(hass)
    assert "spook__read" in tools
    assert "spook__change" not in tools
    assert "spook__stub_reading" not in tools

    _add(hass, _ChangingTool)
    tools = _tools(hass)
    assert set(tools) >= _DOORS
    assert "spook__stub_changing" not in tools
    assert list(tools) == sorted(tools)


async def test_a_door_lists_what_it_can_run(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test a door lists its own kind only, front included, doors and far away not."""
    _add(hass, _ReadingTool, _ChangingTool, _FarAwayTool)

    result = await _call(hass, "spook__read", hass_admin_user)

    assert not result.error
    names = [tool["name"] for tool in result.data["tools"]]
    assert names == sorted(names)
    assert result.data["total"] == len(names)
    assert "spook__stub_reading" in names
    assert "spook__list_ghosts" in names
    assert "spook__stub_changing" not in names
    assert "spook__fix_ghost" not in names
    assert "spook__stub_far_away" not in names
    assert not set(names) & _DOORS
    assert {
        "name": "spook__stub_reading",
        "title": "Read a stub",
        "description": "Reads a stub.",
    } in result.data["tools"]

    result = await _call(hass, "spook__change", hass_admin_user)

    names = [tool["name"] for tool in result.data["tools"]]
    assert "spook__stub_changing" in names
    assert "spook__fix_ghost" in names
    assert "spook__stub_reading" not in names
    assert not set(names) & _DOORS


async def test_a_door_says_so_for_a_tool_it_does_not_have(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test an unknown name, or one far away, comes back with the list."""
    _add(hass, _ReadingTool, _FarAwayTool)

    for name in ("spook__nope", "stub_far_away"):
        result = await _call(hass, "spook__read", hass_admin_user, tool=name)

        assert result.error
        assert "no tool" in result.data["error"]
        names = [tool["name"] for tool in result.data["tools"]]
        assert "spook__stub_reading" in names
        assert "spook__stub_far_away" not in names

    assert not _runs(hass)


async def test_a_door_sends_the_other_kind_to_the_other_door(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test a tool asked for at the wrong door is not run, and the right one named."""
    _add(hass, _ReadingTool, _ChangingTool)

    result = await _call(hass, "spook__read", hass_admin_user, tool="stub_changing")
    assert result.error
    assert "spook__change" in result.data["error"]

    result = await _call(
        hass,
        "spook__change",
        hass_admin_user,
        tool="spook__stub_reading",
        arguments={"what": "boo"},
    )
    assert result.error
    assert "spook__read" in result.data["error"]

    assert not _runs(hass)


async def test_a_door_does_not_run_a_door(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test a door asked to run a door, of either kind, refuses."""
    _add(hass, _ReadingTool, _ChangingTool)

    for door, other in (
        ("spook__read", "spook__read"),
        ("spook__read", "change"),
        ("spook__change", "spook__change"),
        ("spook__change", "spook__read"),
    ):
        result = await _call(
            hass,
            door,
            hass_admin_user,
            tool=other,
            arguments={"tool": "stub_reading"},
        )
        assert result.error
        assert "door" in result.data["error"]

    assert not _runs(hass)


async def test_a_door_runs_a_tool_and_hands_its_result_back(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test a tool run through its door validates, runs, and answers unchanged."""
    _add(hass, _ReadingTool)

    result = await _call(
        hass,
        "spook__read",
        hass_admin_user,
        tool="stub_reading",
        arguments={"what": "boo", "count": "2"},
    )

    assert result == ToolResult(
        data={"ran": "spook__stub_reading", "args": {"what": "boo", "count": 2}}
    )
    assert _runs(hass) == [("spook__stub_reading", {"what": "boo", "count": 2})]

    # One in the front is just as reachable, which saves a model a guess.
    result = await _call(
        hass, "spook__read", hass_admin_user, tool="spook__list_ghosts"
    )
    assert not result.error
    assert result.data == {"total": 0, "ghosts": []}


async def test_a_door_to_change_wants_a_user(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test a change through a door without a user is refused, and not done."""
    _add(hass, _ChangingTool)

    result = await _call(hass, "spook__change", None, tool="stub_changing")

    assert result.error
    assert "no user" in result.data["error"]
    assert not _runs(hass)

    result = await _call(hass, "spook__change", hass_admin_user, tool="stub_changing")

    assert not result.error
    assert _runs(hass) == [("spook__stub_changing", {})]


async def test_a_door_refuses_who_is_not_an_administrator(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Test a user who is not an administrator gets nothing through a door."""
    _add(hass, _ReadingTool, _ChangingTool)

    for door, tool, arguments in (
        ("spook__read", "stub_reading", {"what": "boo"}),
        ("spook__read", None, {}),
        ("spook__change", "stub_changing", {}),
    ):
        tool_args: dict[str, Any] = {"arguments": arguments}
        if tool is not None:
            tool_args["tool"] = tool
        result = await _call(hass, door, hass_read_only_user, **tool_args)

        assert result.error
        assert "administrators" in result.data["error"]
        assert "tools" not in result.data

    assert not _runs(hass)


async def test_a_door_hands_back_the_parameters_when_they_do_not_fit(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test arguments that do not validate come back with what the tool takes."""
    _add(hass, _ReadingTool)

    for arguments in ({}, {"what": "boo", "count": 0}, {"what": "boo", "nope": 1}):
        result = await _call(
            hass,
            "spook__read",
            hass_admin_user,
            tool="stub_reading",
            arguments=arguments,
        )

        assert result.error
        assert "do not fit" in result.data["error"]
        assert result.data["tool"] == "spook__stub_reading"
        assert result.data["parameters"] == llm_tools.tool_schema(_ReadingTool)

    assert result.data["parameters"]["required"] == ["what"]
    assert set(result.data["parameters"]["properties"]) == {"what", "count"}
    assert not _runs(hass)


async def test_a_door_reads_arguments_gemini_wrapped(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test arguments handed over as a JSON string are read as the object.

    Gemini takes no object without fixed properties, so Home Assistant's
    Gemini integration offers `arguments` as an object holding one string,
    `json`.
    """
    _add(hass, _ReadingTool)

    result = await _call(
        hass,
        "spook__read",
        hass_admin_user,
        tool="stub_reading",
        arguments={"json": json.dumps({"what": "boo"})},
    )
    assert not result.error
    assert result.data["args"] == {"what": "boo", "count": 1}

    result = await _call(
        hass,
        "spook__read",
        hass_admin_user,
        tool="stub_reading",
        arguments={"json": "{not json"},
    )
    assert result.error
    assert "The arguments are not valid JSON" in result.data["error"]

    result = await _call(
        hass,
        "spook__read",
        hass_admin_user,
        tool="stub_reading",
        arguments={"json": "[]"},
    )
    assert result.error
    assert result.data["error"] == "The arguments should be a JSON object."

    assert _runs(hass) == [("spook__stub_reading", {"what": "boo", "count": 1})]


def test_the_prompt_names_what_is_handed_out(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the prompt points only at tools a model actually has."""
    prompt = _offered(hass).prompt

    assert prompt.startswith("Spook is a Home Assistant integration")
    assert "spook__find_usages" in prompt
    assert "spook__list_features" in prompt
    assert "spook__read" not in prompt
    assert "spook__change" not in prompt

    _add(hass, _ReadingTool)
    prompt = _offered(hass).prompt

    assert "spook__read" in prompt
    assert "spook__change" not in prompt

    _add(hass, _ChangingTool)
    prompt = _offered(hass).prompt

    assert "spook__change and spook__read" in prompt

    monkeypatch.setitem(
        hass.data,
        llm_tools.DATA_TOOLS,
        [
            tool
            for tool in hass.data[llm_tools.DATA_TOOLS]
            if tool.name != "spook__find_usages"
        ],
    )
    prompt = _offered(hass).prompt

    assert "spook__find_usages" not in prompt
    assert "spook__list_features" in prompt


def _size(tool: type[llm_tools.AbstractSpookTool]) -> int:
    """Return the size of a tool's definition, the way a client receives it."""
    return len(
        json.dumps(
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": llm_tools.tool_schema(tool),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def test_the_front_stays_within_its_budget(hass: HomeAssistant) -> None:
    """Test what goes along with every request stays below a fixed size.

    The doors count, even while nothing is behind them yet, and so does the
    longest prompt that can be handed out.
    """
    found = hass.data[llm_tools.DATA_TOOLS]
    front = [tool for tool in found if tool.in_front]
    doors = [tool for tool in found if tool.is_door]
    assert {door.name for door in doors} == _DOORS

    prompt = llm_tools.build_prompt([*front, *doors])
    size = sum(_size(tool) for tool in [*front, *doors]) + len(prompt)

    assert size <= _FRONT_BUDGET, (
        f"The front is {size} characters, above its budget of {_FRONT_BUDGET}. "
        "Everything in it goes along with every request. A tool belongs behind "
        "a door unless it has to be in the front."
    )
