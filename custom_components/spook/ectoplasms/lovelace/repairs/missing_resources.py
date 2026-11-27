"""Spook - Your homie."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ....dashboard_resources import is_yaml_managed
from ..resource_repairs import AbstractSpookDashboardResourcesRepair

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


class SpookRepair(AbstractSpookDashboardResourcesRepair):
    """Spook repair finds dashboard resources pointing at missing files.

    A dashboard resource served from ``/local/`` or ``/hacsfiles/`` whose
    file was removed (often after uninstalling a custom card) silently
    fails to load in the browser.
    """

    repair = "lovelace_missing_resources"

    async def _async_inspect_resources(self, resources: Any) -> None:
        """Report the local resources whose file is not there."""
        to_check: dict[str, Path] = {}
        for item in resources.async_items() or []:
            if (url := item.get("url")) and (
                path := _local_path(self.hass, url)
            ) is not None:
                to_check[url] = path

        missing = await self.hass.async_add_executor_job(self._find_missing, to_check)
        if missing:
            # Where to go and fix it depends on where the resources live.
            # Sending somebody with a YAML configuration to the Resources page
            # sends them to a screen that cannot change what they came for.
            self.async_create_issue(
                issue_id=self.repair,
                references=missing,
                translation_key=(
                    f"{self.repair}_yaml" if is_yaml_managed(resources) else self.repair
                ),
                translation_placeholders={
                    "resources": "\n".join(f"- `{url}`" for url in sorted(missing)),
                },
            )

    @staticmethod
    def _find_missing(to_check: dict[str, Path]) -> set[str]:
        """Return the URLs whose mapped file does not exist."""
        return {url for url, path in to_check.items() if not path.exists()}
