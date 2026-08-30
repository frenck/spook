"""Spook - Your homie."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_LOVELACE_UPDATED

from ....const import LOGGER
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from collections.abc import Iterable

# Resources served from the configuration directory, where the path is the
# file. Anything else is somebody else's server, and a query string there can
# genuinely change what comes back.
_LOCAL_PREFIXES = ("/local/", "/hacsfiles/")


def _is_local(url: str) -> bool:
    """Return whether this URL maps to a file Home Assistant serves itself."""
    return url.startswith(_LOCAL_PREFIXES)


def _group_key(url: str) -> str:
    """Return what makes two resources the same thing.

    For a local file the query string is cache busting, so `card.js?v=1` and
    `card.js?v=2` are one file listed twice, and the browser loading both is
    what breaks the card. For anything else the query can be the difference
    between two real files, so only an exact repeat counts.
    """
    if _is_local(url):
        return url.split("?", 1)[0]
    return url


def _describe(key: str, urls: list[str]) -> str:
    """Return one line naming a duplicated resource."""
    unique = sorted(set(urls))
    if len(unique) == 1:
        # Name it as it appears in the list. For a local resource the key is
        # the path with the query taken off, so reporting that would send
        # somebody looking for a URL that is not in there.
        return f"- `{unique[0]}`, listed {len(urls)} times"
    listed = ", ".join(f"`{url}`" for url in unique)
    return f"- `{key}`, listed {len(urls)} times: {listed}"


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds the same dashboard resource listed more than once.

    Updating a custom card by adding a resource for the new version, instead
    of editing the one already there, leaves both behind. The browser fetches
    both, the card tries to register itself twice, and the second attempt
    throws. The card is then broken in a way that points at the card rather
    than at the resource list.
    """

    domain = DOMAIN
    repair = "lovelace_duplicate_resources"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
    }
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        self.possible_issue_ids.add(self.repair)

        if (resources := self.hass.data[DOMAIN].resources) is None:
            return

        # Storage-mode resources load the first time somebody asks for them,
        # which is normally the dashboard, long after Spook looks.
        await resources.async_get_info()

        if not (duplicated := self._find_duplicates(resources.async_items() or [])):
            return

        self.async_create_issue(
            issue_id=self.repair,
            translation_placeholders={
                "resources": "\n".join(
                    _describe(key, duplicated[key]) for key in sorted(duplicated)
                ),
            },
        )

    @staticmethod
    def _find_duplicates(items: Iterable[dict]) -> dict[str, list[str]]:
        """Return every resource listed more than once, by what it points at."""
        seen: dict[str, list[str]] = defaultdict(list)
        for item in items:
            if url := item.get("url"):
                seen[_group_key(url)].append(url)

        return {key: urls for key, urls in seen.items() if len(urls) > 1}
