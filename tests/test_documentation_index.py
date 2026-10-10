"""Tests that the documentation index covers everything Spook ships.

Both of these gaps are invisible from the inside. An action missing from the
list is only noticed by somebody who already knows it exists and cannot find
it, and a page with no card is only noticed by somebody who was not looking
for it in the first place.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
SPOOK = ROOT / "custom_components" / "spook"
DOCS = ROOT / "documentation"

# Spook ships well over eighty actions and twenty-odd integration pages, so
# anything near this means a regex stopped matching rather than a real drop.
AT_LEAST_THIS_MANY = 50

ACTIONS = (DOCS / "actions.md").read_text()
CARDS = (DOCS / "enhanced_integrations.md").read_text()
TOC = (DOCS / "_toc.yml").read_text()

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


def _slug(heading: str) -> str:
    """Turn a heading into the anchor the site gives it.

    Punctuation is dropped rather than replaced, so "Update an entity's ID"
    becomes `update-an-entitys-id` and not `update-an-entity-s-id`. Getting
    that backwards is how the link to that very section came to be broken.
    """
    kept = re.sub(r"[^a-z0-9 -]+", "", heading.lower())
    return re.sub(r"[ -]+", "-", kept).strip("-")


def _page(reference: str) -> Path | None:
    """Return the file a documentation reference points at.

    The site slugifies underscores into hyphens, and the references in the
    action list are written both ways, so both have to resolve.
    """
    for candidate in (reference, reference.replace("-", "_")):
        if (path := DOCS / f"{candidate}.md").exists():
            return path
    return None


def test_the_scan_finds_the_entries() -> None:
    """Guard the two regexes, which would otherwise pass by matching nothing."""
    assert len(_LISTED.findall(ACTIONS)) > AT_LEAST_THIS_MANY
    assert len(_shipped_actions()) > AT_LEAST_THIS_MANY


def test_every_action_is_in_the_list() -> None:
    """An action nobody can find might as well not have shipped."""
    listed = {match[0] for match in _LISTED.findall(ACTIONS)}
    missing = _shipped_actions() - listed
    assert not missing, f"not in documentation/actions.md: {sorted(missing)}"


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


def _pages() -> set[str]:
    """Return the integration pages the table of contents carries."""
    return set(re.findall(r"- file: integrations/(\w+)", TOC))


@pytest.mark.parametrize("direction", ["page-without-card", "card-without-page"])
def test_pages_and_cards_agree(direction: str) -> None:
    """Pages and cards have to line up in both directions.

    The card grid is how these pages get found, so one without a card is only
    reachable by guessing its URL.
    """
    pages = _pages()
    cards = set(re.findall(r"\]\(integrations/(\w+)\)", CARDS))
    assert pages, "no integration pages found in the table of contents"

    if direction == "page-without-card":
        assert not pages - cards, (
            f"no card on the integrations page: {sorted(pages - cards)}"
        )
    else:
        assert not cards - pages, f"card points at no page: {sorted(cards - pages)}"


def test_every_documentation_link_points_at_a_page_that_exists() -> None:
    """A link into a page that was renamed reads fine and goes nowhere."""
    broken = []
    for match in _LISTED.finditer(ACTIONS):
        if not (doc := match["doc"]):
            continue
        if _page(doc.split("#", 1)[0]) is None:
            broken.append(f"{match[0]} -> {doc}")
    assert not broken, f"documentation links with no page: {broken}"


def test_every_documentation_anchor_points_at_a_real_heading() -> None:
    """Anchors rot quietly when a heading is reworded."""
    broken = []
    for match in _LISTED.finditer(ACTIONS):
        if not (doc := match["doc"]) or "#" not in doc:
            continue
        page, _, anchor = doc.partition("#")
        if (path := _page(page)) is None:
            continue
        text = path.read_text()
        headings = {
            _slug(heading) for heading in re.findall(r"^#+ (.+)$", text, re.MULTILINE)
        }
        headings |= set(re.findall(r"^\(([a-z0-9-]+)\)=$", text, re.MULTILINE))
        if anchor not in headings:
            broken.append(f"{match[0]} -> {doc}")
    assert not broken, f"documentation anchors with no heading: {broken}"
