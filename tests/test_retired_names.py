"""Home Assistant renamed Developer Tools, so Spook stops calling it that.

It is `Settings` > `Tools` now, and the frontend has no "Developer tools"
string left at all. Spook said the old name in a repair, in a glossary term,
and in eighty-five places across the documentation that linked to that term.
Reported as #1526, against the one place the reporter happened to look.

Two mentions survive on purpose, both saying what the thing used to be called
so that somebody following an older guide can tell they are in the right place.
They are spelled out here rather than matched loosely, so editing one is a
decision somebody makes rather than a hole that widens on its own.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).parents[1]
SPOOK = ROOT / "custom_components" / "spook"
DOCUMENTATION = ROOT / "documentation"

# Deliberately loose about what sits between the two words. Eight captions
# said "developer actions tools", which a tighter matcher walked past.
_RETIRED = re.compile(r"developer(?:[ _-]\w+)?[ _-]?tools", re.IGNORECASE)

# What people will still find in older guides, said once in each place so that
# the rename is explained rather than silently applied.
_DELIBERATE = (
    (
        'These were called the "developer tools" and lived in their own place in '
        "the sidebar until Home Assistant moved and renamed them in 2026."
    ),
    "That page was called Developer Tools and sat in",
)

# My Home Assistant redirect and badge names. These are identifiers in
# somebody else's API, not prose, and they have not been renamed.
_NOT_OURS = re.compile(r"my\.home-assistant\.io/(?:redirect|badges)/[a-z_]+")


def _lines_naming_it() -> list[str]:
    """Return every line still calling it that, minus the ones allowed above."""
    found = []
    for path in [
        *DOCUMENTATION.rglob("*.md"),
        *SPOOK.rglob("*.py"),
        *SPOOK.rglob("*.json"),
        # The action, trigger and condition descriptors are read by people in
        # the UI as much as anything else here is.
        *SPOOK.rglob("*.yaml"),
    ]:
        if "_build" in str(path):
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            # Cut the allowed phrases out rather than passing over the whole
            # line that carries one. A line is allowed to explain the rename
            # once, not to become somewhere the old name can be hidden.
            stripped = _NOT_OURS.sub("", line)
            for allowed in _DELIBERATE:
                stripped = stripped.replace(allowed, "")

            if _RETIRED.search(stripped):
                found.append(f"{path.relative_to(ROOT)}:{number}")
    return found


def test_the_deliberate_mentions_are_still_there() -> None:
    """Otherwise the check below passes by having nothing to allow."""
    everything = "\n".join(
        p.read_text()
        for p in [*DOCUMENTATION.rglob("*.md"), *SPOOK.rglob("*.py")]
        if "_build" not in str(p)
    )

    for allowed in _DELIBERATE:
        assert allowed in everything, (
            f"the note explaining the rename is gone: {allowed!r}"
        )


def test_nothing_calls_it_developer_tools_any_more() -> None:
    """It is Settings > Tools, and has been since Home Assistant moved it."""
    naming_it = _lines_naming_it()

    assert not naming_it, "these still call it Developer Tools: " + ", ".join(naming_it)
