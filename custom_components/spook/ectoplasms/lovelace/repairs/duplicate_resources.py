"""Spook - Your homie."""

from __future__ import annotations

from typing import Any

from ....dashboard_resources import describe, find_duplicates, target_of
from ..resource_repairs import AbstractSpookDashboardResourcesRepair


class SpookRepair(AbstractSpookDashboardResourcesRepair):
    """Spook repair finds the same dashboard resource listed more than once.

    Updating a custom card by adding a resource for the new version, instead
    of editing the one already there, leaves both behind. The browser fetches
    both, the card tries to register itself twice, and the second attempt
    throws. The card is then broken in a way that points at the card rather
    than at the resource list.
    """

    repair = "lovelace_duplicate_resources"

    async def _async_inspect_resources(self, resources: Any) -> None:
        """Report every resource that is listed more than once."""
        items = list(resources.async_items() or [])
        for key, urls in find_duplicates(items).items():
            self.possible_issue_ids.add(key)
            self.async_create_issue(
                issue_id=key,
                is_fixable=True,
                data={
                    "duplicate_resource_url": key,
                    "resource": target_of(key),
                    "resources": describe(key, urls),
                    "count": str(len(urls)),
                },
                translation_placeholders={
                    "resource": target_of(key),
                    "resources": describe(key, urls),
                    "count": str(len(urls)),
                },
            )
