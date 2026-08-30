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

        # Every component that loads pokes this repair, and Lovelace is not
        # necessarily one of the ones already up when that happens.
        if (lovelace := self.hass.data.get(DOMAIN)) is None:
            return

        if (resources := lovelace.resources) is None:
            return

        # Storage-mode resources load the first time somebody asks for them,
        # which is normally the dashboard, long after Spook looks.
        await resources.async_get_info()

        # Resources listed in YAML are static, so there is nothing to offer
        # beyond pointing at them: the fix has to happen in the file.
        can_remove = hasattr(resources, "async_delete_item")

        items = list(resources.async_items() or [])
        for key, urls in find_duplicates(items).items():
            self.possible_issue_ids.add(key)
            self.async_create_issue(
                issue_id=key,
                is_fixable=can_remove,
                data={"duplicate_resource_url": key, "resource": key},
                translation_placeholders={
                    "resource": key,
                    "resources": describe(key, urls),
                    "count": str(len(urls)),
                },
            )
