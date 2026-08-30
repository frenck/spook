"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_LOVELACE_UPDATED

from ....const import LOGGER
from ....dashboard_resources import describe, find_duplicates
from ....repairs import AbstractSpookRepair


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

        # Reached straight rather than guarded: Lovelace is a hard dependency
        # in the manifest, so Home Assistant has set it up before Spook. A
        # guard here would be worse than none, because returning early counts
        # as a clean inspection and cleanup would then delete every issue this
        # repair has, ignored ones included. If that invariant ever breaks, a
        # KeyError is what should happen: it leaves the bookkeeping intact.
        if (resources := self.hass.data[DOMAIN].resources) is None:
            return

        # Storage-mode resources load the first time somebody asks for them,
        # which is normally the dashboard, long after Spook looks.
        await resources.async_get_info()

        items = list(resources.async_items() or [])
        for key, urls in find_duplicates(items).items():
            self.possible_issue_ids.add(key)
            self.async_create_issue(
                issue_id=key,
                is_fixable=True,
                data={
                    "duplicate_resource_url": key,
                    "resource": key,
                    "resources": describe(key, urls),
                    "count": str(len(urls)),
                },
                translation_placeholders={
                    "resource": key,
                    "resources": describe(key, urls),
                    "count": str(len(urls)),
                },
            )
