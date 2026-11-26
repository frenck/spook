"""Tests that the documentation index covers everything Spook ships.

This gap is invisible from the inside. An action missing from the list is
only noticed by somebody who already knows it exists and cannot find it.

The integration catalog needs no such test: it lists every page in its
section by itself, so a page cannot be left off it.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import yaml

from tests.documentation_helpers import headings, page

ROOT = Path(__file__).parents[1]
SPOOK = ROOT / "custom_components" / "spook"

# Spook ships well over eighty actions and twenty-odd integration pages, so
# anything near this means a regex stopped matching rather than a real drop.
AT_LEAST_THIS_MANY = 50

ACTIONS = page("actions").read_text()

# Every entry is a name in backticks followed by the deep link that offers it.
_LISTED = re.compile(
    r"^`([a-z_]+\.[a-z_]+)`, \[Try this action\]\((?P<link>[^)]+)\)"
    r"(?:, \[documentation\]\((?P<doc>[^)]+)\))?",
    re.MULTILINE,
)


def _domains() -> list[str]:
    """Return the domains Spook adds actions to, longest first.

    `services.yaml` joins the two halves with an underscore, and plenty of
    domains contain one themselves, so the split has to know the domains
    rather than guess at the first underscore.
    """
    ectoplasms = SPOOK / "ectoplasms"
    return sorted(
        (path.name for path in ectoplasms.iterdir() if (path / "services").is_dir()),
        key=len,
        reverse=True,
    )


def _shipped_actions() -> set[str]:
    """Return every action Spook registers, read off services.yaml.

    That file is what Home Assistant serves to the UI, so it is the list a
    user can actually see, and therefore the list they can fail to find in
    the documentation. Reading the modules instead would miss the actions
    that inherit their name from another one.
    """
    domains = _domains()
    services = yaml.safe_load((SPOOK / "services.yaml").read_text())

    actions = set()
    for key in services:
        for domain in domains:
            if key.startswith(f"{domain}_"):
                actions.add(f"{domain}.{key[len(domain) + 1 :]}")
                break
        else:
            # Spook's own actions are keyed bare, without a domain in front.
            actions.add(f"spook.{key}")
    return actions


def test_the_scan_finds_the_entries() -> None:
    """Guard the two regexes, which would otherwise pass by matching nothing."""
    assert len(_LISTED.findall(ACTIONS)) > AT_LEAST_THIS_MANY
    assert len(_shipped_actions()) > AT_LEAST_THIS_MANY


def test_every_action_is_in_the_list() -> None:
    """An action nobody can find might as well not have shipped."""
    listed = {match[0] for match in _LISTED.findall(ACTIONS)}
    missing = _shipped_actions() - listed
    assert not missing, f"not in the actions reference: {sorted(missing)}"


def test_no_action_is_claimed_by_two_entries() -> None:
    """Entries get copied from the one above and only half corrected.

    Device: Enable carried the disable action, its link and its documentation
    for a long time, which reads as a working entry right up until somebody
    uses it.
    """
    named = [match[0] for match in _LISTED.findall(ACTIONS)]
    twice = sorted(action for action, count in Counter(named).items() if count > 1)
    assert not twice, f"listed under more than one heading: {twice}"


def test_no_documentation_link_is_shared_by_two_entries() -> None:
    """The other half of the same copy: the name fixed, the link left behind."""
    docs = [m["doc"] for m in _LISTED.finditer(ACTIONS) if m["doc"]]
    twice = sorted(link for link, count in Counter(docs).items() if count > 1)
    assert not twice, f"documentation link used by more than one entry: {twice}"


def test_every_documentation_link_points_at_a_page_that_exists() -> None:
    """A link into a page that was renamed reads fine and goes nowhere."""
    broken = []
    for match in _LISTED.finditer(ACTIONS):
        if not (doc := match["doc"]):
            continue
        if page(doc.split("#", 1)[0].strip("/")) is None:
            broken.append(f"{match[0]} -> {doc}")
    assert not broken, f"documentation links with no page: {broken}"


def test_every_documentation_anchor_points_at_a_real_heading() -> None:
    """Anchors rot quietly when a heading is reworded."""
    broken = []
    for match in _LISTED.finditer(ACTIONS):
        if not (doc := match["doc"]) or "#" not in doc:
            continue
        slug, _, anchor = doc.partition("#")
        if (path := page(slug.strip("/"))) is None:
            continue
        if anchor not in {found for _, _, found in headings(path.read_text())}:
            broken.append(f"{match[0]} -> {doc}")
    assert not broken, f"documentation anchors with no heading: {broken}"


def test_every_action_is_in_a_group() -> None:
    """The site groups the actions page by what comes before the colon.

    `## Areas: Create an area` lands under Areas. A heading without a group
    ends up in a group of its own called Other, at the bottom of the page.
    Give it a group, and keep its old anchor with `{#...}` if it had one.
    """
    ungrouped = [text for _, text, _ in headings(ACTIONS) if ": " not in text]
    assert not ungrouped, f"actions without a group: {ungrouped}"
