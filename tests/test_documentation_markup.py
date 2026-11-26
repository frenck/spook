"""Tests for the component markup in the documentation.

A component in the documentation is closed by a line of colons. Written
straight under a list, Markdown reads that line as more of the last list item,
and prettier then indents it into the list. The component never closes, and
everything below it on the page ends up inside it: once, the whole Repairs
section of six pages sat hidden in a collapsed "Known limitations" box.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.documentation_helpers import CONTENT

if TYPE_CHECKING:
    from pathlib import Path

_FENCE = re.compile(r"^\s*:{2,}\s*$")
_CODE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)

PAGES = sorted(CONTENT.rglob("*.md"))

# There are well over eighty pages, so anything near this means the glob
# stopped matching rather than that pages went missing.
AT_LEAST_THIS_MANY = 50


def _lines(path: Path) -> list[str]:
    """Return the lines of a page, with its code blocks blanked out."""
    return _CODE.sub(lambda m: "\n" * m.group(0).count("\n"), path.read_text()).split(
        "\n"
    )


def test_the_pages_are_found() -> None:
    """Guard the tests below, which would otherwise pass on nothing."""
    assert len(PAGES) > AT_LEAST_THIS_MANY


@pytest.mark.parametrize("path", PAGES, ids=lambda path: path.stem)
def test_closing_fences_are_not_indented(path: Path) -> None:
    """An indented closing fence has already been swallowed by a list."""
    indented = [
        number
        for number, line in enumerate(_lines(path), start=1)
        if _FENCE.match(line) and line != line.lstrip()
    ]
    assert not indented, f"indented closing fence on line(s) {indented}"


@pytest.mark.parametrize("path", PAGES, ids=lambda path: path.stem)
def test_closing_fences_follow_a_blank_line(path: Path) -> None:
    """Straight under text, the next prettier run swallows the fence."""
    lines = _lines(path)
    cramped = [
        number
        for number, line in enumerate(lines, start=1)
        if _FENCE.match(line)
        and number > 1
        and lines[number - 2].strip()
        and not _FENCE.match(lines[number - 2])
    ]
    assert not cramped, f"closing fence right under text on line(s) {cramped}"


# MyST, which this documentation was written in before: a directive like
# ```{figure} or :::{note}, or a {term}`role`. Left over, it shows up as
# literal text on the page. The conversion missed a few that were indented
# inside a numbered list once.
_MYST = re.compile(r"(?:`{3,}|:{3,})\{[a-z-]+\}|\{term\}`")


@pytest.mark.parametrize("path", PAGES, ids=lambda path: path.stem)
def test_no_myst_left(path: Path) -> None:
    """The site does not read MyST, so any that is left is shown as text."""
    found = [
        number
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if _MYST.search(line)
    ]
    assert not found, f"MyST markup on line(s) {found}"
