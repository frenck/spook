"""Read Spook's documentation the way the site serves it."""

from __future__ import annotations

from pathlib import Path
import re

CONTENT = Path(__file__).parents[1] / "documentation" / "content"

# `:term[entities]{to="entity"}` shows "entities". The heading's anchor is
# made from what shows, so the markup has to go first.
_TERM = re.compile(r":term\[([^\]]*)\](?:\{[^}]*\})?")

# A heading can keep an anchor it was linked by under an older name, like
# `## MIT License {#mit}`.
_EXPLICIT = re.compile(r"\s*\{#([a-z0-9-]+)\}\s*$")

_CODE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def page(slug: str) -> Path | None:
    """Return the file the site serves at `/<slug>`, if there is one.

    Files are named after their address, behind the number that orders them
    in their section, like `06.reference/01.actions.md` for `/actions`.
    """
    found = list(CONTENT.glob(f"*/[0-9][0-9].{slug}.md"))
    return found[0] if len(found) == 1 else None


def anchor(text: str) -> str:
    """Return the anchor the site gives a heading.

    The same rule as `documentation/shared/utils/anchor.ts`, which keeps the
    anchors MyST gave out, because released versions of Spook link to them.
    """
    text = re.sub(r"[`*_]", "", _TERM.sub(r"\1", text)).strip().lower()
    text = re.sub("['\u2019]", "", text)
    text = re.sub(r"[^a-z0-9-]", "-", text)
    text = re.sub(r"^([0-9-])", r"id-\1", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def headings(text: str) -> list[tuple[int, str, str]]:
    """Return every heading on a page as its level, text and anchor."""
    found = []
    seen: dict[str, int] = {}
    for hashes, line in re.findall(
        r"^(#{2,6}) (.+)$", _CODE.sub("", text), re.MULTILINE
    ):
        heading = _EXPLICIT.sub("", line)
        if explicit := _EXPLICIT.search(line):
            slug = explicit.group(1)
        else:
            slug = anchor(heading)

        # The second heading with the same anchor gets `-1`, and so on.
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        found.append((len(hashes), heading, f"{slug}-{count}" if count else slug))
    return found
