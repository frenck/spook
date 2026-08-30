"""Spook - Your homie. Shared rules for dashboard resources.

Both the repair that finds duplicated resources and the fix flow that clears
them need to agree on what makes two resources the same thing. They live on
opposite sides of an import cycle, so the rule lives here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Resources served out of the configuration directory, where the path is the
# file. Anything else is somebody else's server, and a query string there can
# genuinely change what comes back.
_LOCAL_PREFIXES = ("/local/", "/hacsfiles/")

# Separates the resource type from what it points at, in the key that decides
# whether two resources are the same one.
_SEPARATOR = "|"


def is_local(url: str) -> bool:
    """Return whether this URL maps to a file Home Assistant serves itself."""
    return url.startswith(_LOCAL_PREFIXES)


def _target(url: str) -> str:
    """Return what a URL points at, ignoring cache busting on local files.

    For a local file the query string is cache busting, so `card.js?v=1` and
    `card.js?v=2` are one file, and the browser loading both is what breaks
    the card. For anything else the query can be the difference between two
    real files, so only an exact repeat counts.
    """
    if is_local(url):
        return url.split("?", 1)[0]
    return url


def group_key(item: dict) -> str:
    """Return what makes two resources the same thing.

    The type is part of it. Home Assistant loads a `module` differently from a
    `css`, so the same URL under two types is two different instructions, not
    a repeat. Clearing one of those would take away something that was meant
    to be there.
    """
    return f"{item.get('type', '')}{_SEPARATOR}{_target(item.get('url', ''))}"


def target_of(key: str) -> str:
    """Return the part of a key worth showing somebody."""
    return key.split(_SEPARATOR, 1)[-1]


def find_duplicates(items: Iterable[dict]) -> dict[str, list[str]]:
    """Return every resource listed more than once, by what it points at."""
    seen: dict[str, list[str]] = {}
    for item in items:
        if item.get("url"):
            seen.setdefault(group_key(item), []).append(item["url"])

    return {key: urls for key, urls in seen.items() if len(urls) > 1}


def describe(key: str, urls: list[str]) -> str:
    """Return one line naming a duplicated resource."""
    unique = sorted(set(urls))
    if len(unique) == 1:
        # Name it as it appears in the list. For a local resource the target
        # is the path with the query taken off, so reporting that would send
        # somebody looking for a URL that is not in there.
        return f"- `{unique[0]}`, listed {len(urls)} times"

    listed = ", ".join(f"`{url}`" for url in unique)
    return f"- `{target_of(key)}`, listed {len(urls)} times: {listed}"


def redundant_item_ids(items: Iterable[dict], key: str) -> list[str]:
    """Return the IDs of the copies to clear, keeping one.

    The one kept is the last, which is the most recently added. For the case
    this exists to clean up, a card updated by adding a resource for the new
    version instead of editing the old one, that is the version somebody
    actually meant to end up with.
    """
    matching = [item for item in items if item.get("url") and group_key(item) == key]
    return [item["id"] for item in matching[:-1] if item.get("id")]
