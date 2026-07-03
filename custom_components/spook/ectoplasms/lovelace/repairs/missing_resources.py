"""Spook - Your homie."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_LOVELACE_UPDATED

from ....const import LOGGER
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Local resource URL prefixes that map to a file on disk. External URLs
# (http/https) and integration-served paths cannot be verified and are
# skipped.
_LOCAL_PREFIX = "/local/"
_HACS_PREFIX = "/hacsfiles/"


def _local_path(hass: HomeAssistant, url: str) -> Path | None:
    """Return the on-disk path a local resource URL maps to, if any."""
    url = url.split("?", 1)[0]
    if url.startswith(_LOCAL_PREFIX):
        return Path(hass.config.path("www", url[len(_LOCAL_PREFIX) :]))
    if url.startswith(_HACS_PREFIX):
        return Path(hass.config.path("www", "community", url[len(_HACS_PREFIX) :]))
    return None


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds dashboard resources pointing at missing files.

    A dashboard resource served from ``/local/`` or ``/hacsfiles/`` whose
    file was removed (often after uninstalling a custom card) silently
    fails to load in the browser.
    """

    domain = DOMAIN
    repair = "lovelace_missing_resources"
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

        to_check: dict[str, Path] = {}
        for item in resources.async_items() or []:
            if (url := item.get("url")) and (
                path := _local_path(self.hass, url)
            ) is not None:
                to_check[url] = path

        missing = await self.hass.async_add_executor_job(self._find_missing, to_check)
        if missing:
            self.async_create_issue(
                issue_id=self.repair,
                translation_placeholders={
                    "resources": "\n".join(f"- `{url}`" for url in sorted(missing)),
                },
            )

    @staticmethod
    def _find_missing(to_check: dict[str, Path]) -> set[str]:
        """Return the URLs whose mapped file does not exist."""
        return {url for url, path in to_check.items() if not path.exists()}
