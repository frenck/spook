"""The real-world corpus, run through what Spook's repairs read.

Every case file is snapshotted in full, which catches any drift, and held to
its own `expect` rules, which say what matters and survive a careless
snapshot update. See the README next to this file.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components import automation, script

from tests.corpus.cases import (
    METADATA_KEYS,
    RULE_KEYS,
    all_case_paths,
    case_paths,
    load_case,
    rule_entries,
)
from tests.corpus.harness import (
    async_component_references,
    async_dashboard_references,
    reference_types,
)

if TYPE_CHECKING:
    from pathlib import Path

    from syrupy.assertion import SnapshotAssertion

    from homeassistant.core import HomeAssistant

    from tests.corpus.cases import Case

KINDS = ("automation", "script", "dashboard")

# How a note says a reference goes unread. Such a case owes an explanation in
# a marker, or it passes with the gap and nobody notices when it closes.
_SAYS_NOT_READ = re.compile(
    r"not read|missed|never (read|checked)|not checked|not looked up|no walk|"
    r"no reader|left out|on purpose|ignored",
    re.IGNORECASE,
)


def _cases(kind: str) -> Any:
    """Return the case files of a kind as parameters, named after the file."""
    return pytest.mark.parametrize("path", case_paths(kind), ids=lambda path: path.stem)


def _broken_rules(case: Case, result: dict[str, Any]) -> list[str]:
    """Return every `expect` rule the result does not keep, described."""
    broken: list[str] = []
    for reference_type, rule in (case.metadata.get("expect") or {}).items():
        reported = set(result.get(reference_type, []))
        broken.extend(
            f"{reference_type}.find: {entry!r} is missing"
            for entry in rule_entries(rule.get("find", []))
            if entry not in reported
        )
        broken.extend(
            f"{reference_type}.not_find: {entry!r} is reported"
            for entry in rule_entries(rule.get("not_find", []))
            if entry in reported
        )
    return broken


def _check_expectations(case: Case, result: dict[str, Any]) -> None:
    """Hold the result to the case's `expect` rules.

    A case marked with a `known_issue` documents something Spook gets wrong
    today: its rules say what should happen, and are expected to break until
    it is fixed. Once they all hold, the mark has to go.
    """
    broken = _broken_rules(case, result)
    known_issue = case.metadata.get("known_issue")

    if known_issue and broken:
        pytest.xfail(f"{case.location}: {known_issue}")
    if known_issue:
        pytest.fail(
            f"{case.location}: every rule holds now, so the known issue is "
            f"fixed; remove `known_issue` from the case. It said: {known_issue}"
        )
    assert not broken, f"{case.location} breaks its expectations:\n" + "\n".join(
        f"- {line}" for line in broken
    )


@_cases("automation")
async def test_automation_case(
    hass: HomeAssistant, snapshot: SnapshotAssertion, path: Path
) -> None:
    """Test what the automation repairs read in an automation case."""
    case = load_case(path)
    result = await async_component_references(hass, automation.DOMAIN, case.config)

    assert result == snapshot
    _check_expectations(case, result)


@_cases("script")
async def test_script_case(
    hass: HomeAssistant, snapshot: SnapshotAssertion, path: Path
) -> None:
    """Test what the script repairs read in a script case."""
    case = load_case(path)
    result = await async_component_references(hass, script.DOMAIN, case.config)

    assert result == snapshot
    _check_expectations(case, result)


@_cases("dashboard")
async def test_dashboard_case(
    hass: HomeAssistant, snapshot: SnapshotAssertion, path: Path
) -> None:
    """Test what the dashboard repairs read in a dashboard, view or card case."""
    case = load_case(path)
    result = await async_dashboard_references(hass, case.config)

    assert result == snapshot
    _check_expectations(case, result)


def _untyped_entries(reference_type: str, rule: dict[str, Any]) -> list[str]:
    """Return a problem for every entry of a rule that YAML did not read as text.

    An unquoted `on` is a boolean to YAML, and would be compared as `True`.
    """
    problems: list[str] = []
    for key, entries in rule.items():
        for entry in entries if isinstance(entries, list) else [entries]:
            values = entry.values() if isinstance(entry, dict) else [entry]
            if all(isinstance(value, str) for value in values):
                continue
            problems.append(
                f"`expect.{reference_type}.{key}` has {entry!r}, which is not "
                "all text; quote it, YAML reads on, off, yes and no as booleans"
            )
    return problems


def _metadata_problems(case: Case) -> list[str]:
    """Return what is wrong with the first document of a case, described."""
    problems: list[str] = []

    for key in ("source", "note"):
        value = case.metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"`{key}` is missing or empty")

    if unknown_keys := set(case.metadata) - METADATA_KEYS:
        problems.append(f"unknown metadata keys: {sorted(unknown_keys)}")

    # Only an absent `expect` means no rules. `expect: []`, `expect: false`
    # or a bare `expect:` is a rule that went missing, not a choice.
    expect = case.metadata.get("expect", {})
    if not isinstance(expect, dict) or ("expect" in case.metadata and not expect):
        problems.append("`expect` is not a mapping of reference types")
        expect = {}

    known_types = reference_types(case.kind)
    for reference_type, rule in expect.items():
        if reference_type not in known_types:
            problems.append(
                f"`expect.{reference_type}` is no reference type for "
                f"{case.kind} cases; known are {sorted(known_types)}"
            )
            continue
        if not isinstance(rule, dict) or not rule or set(rule) - RULE_KEYS:
            problems.append(
                f"`expect.{reference_type}` holds anything but `find` and `not_find`"
            )
            continue
        problems.extend(_untyped_entries(reference_type, rule))

    problems.extend(_mark_problems(case, expect))
    return problems


def _mark_problems(case: Case, expect: dict[str, Any]) -> list[str]:
    """Return what is wrong with how a case marks what goes unread, described.

    A note saying something is not read needs a mark, and a mark lifts that
    check, so it has to give a reason.
    """
    problems: list[str] = []
    if "out_of_scope" in case.metadata:
        problems.extend(_out_of_scope_problems(case.metadata["out_of_scope"], expect))
    if "known_issue" in case.metadata and not _is_reason(case.metadata["known_issue"]):
        problems.append("`known_issue` is not a reason")

    note = " ".join(str(case.metadata.get("note", "")).split())
    marked = {"known_issue", "out_of_scope"} & case.metadata.keys()
    if not marked and (said := _SAYS_NOT_READ.search(note)):
        problems.append(
            f"the note says something goes unread ({said.group(0)!r}); mark it "
            "with `known_issue` or `out_of_scope`, or say it plainer"
        )
    return problems


def _is_reason(value: Any) -> bool:
    """Return whether a mark gives a reason, rather than being empty or a flag."""
    return isinstance(value, str) and bool(value.strip())


def _out_of_scope_problems(reason: Any, expect: dict[str, Any]) -> list[str]:
    """Return what is wrong with an `out_of_scope` mark, described.

    What Spook leaves alone on purpose is pinned as not found, so the day a
    reader starts taking it, the case has to say so.
    """
    problems: list[str] = []
    if not _is_reason(reason):
        problems.append("`out_of_scope` is not a reason")
    if not any(
        isinstance(rule, dict) and rule.get("not_find") for rule in expect.values()
    ):
        problems.append(
            "`out_of_scope` needs a `not_find` rule naming what is left alone"
        )
    return problems


@pytest.mark.parametrize(
    "path",
    all_case_paths(KINDS),
    ids=lambda path: f"{path.parent.name}/{path.stem}",
)
def test_case_file_is_well_formed(path: Path) -> None:
    """Test a case file says where it comes from and asks only what exists."""
    case = load_case(path)
    problems = _metadata_problems(case)

    if not case.config:
        problems.append("the configuration document is empty")
    elif not isinstance(case.config, dict):
        problems.append("the configuration document is not a mapping")

    assert not problems, f"{case.location}:\n" + "\n".join(
        f"- {line}" for line in problems
    )


@pytest.mark.parametrize(
    ("metadata", "problem"),
    [
        pytest.param("expect: []", "`expect` is not a mapping", id="empty list"),
        pytest.param("expect: false", "`expect` is not a mapping", id="false"),
        pytest.param("expect:", "`expect` is not a mapping", id="bare"),
        pytest.param(
            "out_of_scope: not read\nexpect:\n  entities:\n    find: [light.a]",
            "needs a `not_find` rule",
            id="out of scope without not_find",
        ),
        pytest.param(
            "out_of_scope:\nexpect:\n  entities:\n    not_find: [light.a]",
            "`out_of_scope` is not a reason",
            id="out of scope without a reason",
        ),
        pytest.param(
            "known_issue:", "`known_issue` is not a reason", id="bare known issue"
        ),
        pytest.param(
            "known_issue: false",
            "`known_issue` is not a reason",
            id="known issue as a flag",
        ),
    ],
)
def test_malformed_metadata_is_reported(
    tmp_path: Path, metadata: str, problem: str
) -> None:
    """Test metadata that is there but says nothing usable does not pass."""
    path = tmp_path / "automation" / "malformed.yaml"
    path.parent.mkdir()
    path.write_text(
        f"source: here\nnote: malformed\n{metadata}\n---\nalias: Malformed\n",
        encoding="utf-8",
    )

    problems = _metadata_problems(load_case(path))

    assert any(problem in line for line in problems), problems


@pytest.mark.parametrize(
    ("marker", "reported"),
    [
        pytest.param("", True, id="unmarked"),
        pytest.param(
            "out_of_scope: a key of the card's own\n", False, id="out of scope"
        ),
        pytest.param("known_issue: a miss\n", False, id="known issue"),
    ],
)
def test_a_note_about_an_unread_reference_needs_a_marker(
    tmp_path: Path, marker: str, *, reported: bool
) -> None:
    """Test a note saying a reference goes unread is not left without a marker."""
    path = tmp_path / "dashboard" / "unread.yaml"
    path.parent.mkdir()
    path.write_text(
        "source: here\nnote: The map camera is missed.\n"
        f"{marker}expect:\n  entities:\n    not_find: [camera.map]\n"
        "---\ntype: custom:vacuum-card\n",
        encoding="utf-8",
    )

    problems = _metadata_problems(load_case(path))

    assert any("goes unread" in line for line in problems) is reported, problems


def test_every_kind_has_cases() -> None:
    """Test no kind of the corpus is left without a single case."""
    assert all(case_paths(kind) for kind in KINDS)


def test_home_assistant_tags_load_as_text(tmp_path: Path) -> None:
    """Test a tag Home Assistant resolves comes out as its tag and value."""
    path = tmp_path / "automation" / "tags.yaml"
    path.parent.mkdir()
    path.write_text(
        "source: here\nnote: tags\n---\n"
        "entity_id: !input motion_entity\n"
        "password: !secret alarm_code\n"
        "cards: !include_dir_list cards\n",
        encoding="utf-8",
    )

    assert load_case(path).config == {
        "entity_id": "!input motion_entity",
        "password": "!secret alarm_code",
        "cards": "!include_dir_list cards",
    }


def test_a_case_needs_both_documents(tmp_path: Path) -> None:
    """Test a case file without its configuration is turned away."""
    path = tmp_path / "automation" / "half.yaml"
    path.parent.mkdir()
    path.write_text("source: here\nnote: no configuration\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected two"):
        load_case(path)
