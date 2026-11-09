"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from homeassistant.components.frontend import DATA_THEMES
from homeassistant.components.lovelace import DOMAIN
from homeassistant.components.lovelace.const import ConfigNotFound
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_LOVELACE_UPDATED,
    EVENT_THEMES_UPDATED,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from ....const import DOMAIN as SPOOK_DOMAIN, LOGGER
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )

_LOCAL_PREFIX = "/local/"

# Up to whatever ends a link in markdown, HTML or CSS.
_LOCAL_LINK = re.compile(r"/local/([^\s?#\"'()<>]+)")

# Where the Marketplace, and HACS before it, installs dashboard cards.
_MARKETPLACE_FOLDER = "community"

# What the frontend loads as code. A folder holding any of it is a card or
# a theme somebody put up on purpose, images and all.
_FRONTEND_CODE = frozenset({".cjs", ".css", ".js", ".map", ".mjs"})

# Files straight in `www`. No folder can be called this.
_ROOT = "."

# Enough to recognise what it is, without turning the issue into a listing.
_SHOWN = 10


def _collect_local_paths(node: Any, found: set[str]) -> None:
    """Collect every `www` path linked to from anywhere in this config.

    Cards keep their images under all sorts of keys, custom cards most of all,
    so every string is looked at rather than a list of known keys.
    """
    if isinstance(node, str):
        found.update(unquote(path) for path in _LOCAL_LINK.findall(node))
    elif isinstance(node, dict):
        for value in node.values():
            _collect_local_paths(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_local_paths(value, found)


def _is_code(path: Path) -> bool:
    """Return whether the frontend loads this file as code."""
    return path.suffix.lower() in _FRONTEND_CODE


def _is_hidden(path: Path, www: Path) -> bool:
    """Return whether a file is, or sits in, something hidden."""
    return any(part.startswith(".") for part in path.relative_to(www).parts)


def _public_files(www: Path, in_use: set[str]) -> dict[str, list[str]]:
    """Return the files nobody seems to have put up on purpose, by folder."""
    if not www.is_dir():
        return {}

    candidates: dict[str, list[Path]] = {}
    for entry in www.iterdir():
        if entry.name.startswith(".") or entry.name == _MARKETPLACE_FOLDER:
            continue

        if entry.is_file() and not _is_code(entry):
            candidates.setdefault(_ROOT, []).append(entry)
        elif entry.is_dir() and not entry.is_symlink():
            files = [
                path
                for path in entry.rglob("*")
                if path.is_file() and not _is_hidden(path, www)
            ]
            if not any(_is_code(path) for path in files):
                candidates[entry.name] = files

    found: dict[str, list[str]] = {}
    for folder, files in candidates.items():
        for path in files:
            if (relative := path.relative_to(www).as_posix()) not in in_use:
                found.setdefault(folder, []).append(relative)

    return {folder: sorted(files) for folder, files in found.items()}


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds files in `www` that anyone can download.

    Home Assistant serves the `www` folder at `/local/` without asking anyone
    to log in, as browsers load cards and images from it with a plain link.
    That is fine for those, but integrations store camera snapshots, print
    previews and the like there too, often without the user knowing.
    """

    domain = DOMAIN
    repair = "lovelace_public_www_files"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
        EVENT_THEMES_UPDATED,
    }
    # Integrations write here at any moment, and nothing announces it.
    inspect_interval = timedelta(hours=1)
    automatically_clean_up_issues = True

    _dashboards: dict[str | None, LovelaceStorage | LovelaceYAML]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._dashboards = self.hass.data[DOMAIN].dashboards
        await super().async_activate()

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        # Collect what dashboards and themes link to, to leave those files alone.
        in_use: set[str] = set()
        for dashboard in list(self._dashboards.values()):
            try:
                config = await dashboard.async_load(force=False)
            except ConfigNotFound:
                # Made up on the fly, so it links to nothing in `www`.
                continue
            except HomeAssistantError:
                # Without its links, files it shows would be reported wrongly.
                LOGGER.warning(
                    "Spook could not read dashboard %s, so it skipped looking "
                    "for public files in www",
                    dashboard.url_path or "lovelace",
                )
                self._async_keep_issues()
                return
            _collect_local_paths(config, in_use)
        _collect_local_paths(self.hass.data.get(DATA_THEMES, {}), in_use)

        public = await self.hass.async_add_executor_job(
            _public_files, Path(self.hass.config.path("www")), in_use
        )

        # Keyed to the folder and not to the files in it: an integration that
        # keeps adding files would otherwise bring an ignored issue back with
        # every one of them.
        for folder, files in public.items():
            url = _LOCAL_PREFIX if folder == _ROOT else f"{_LOCAL_PREFIX}{folder}/"
            self.async_create_issue(
                issue_id=folder,
                translation_placeholders={
                    "folder": url,
                    "count": str(len(files)),
                    "files": "\n".join(
                        f"- `{_LOCAL_PREFIX}{file}`" for file in files[:_SHOWN]
                    ),
                },
            )

    @callback
    def _async_keep_issues(self) -> None:
        """Keep every issue raised before, which the cleanup would remove."""
        prefix = f"{self.repair}_"
        self.issue_ids.update(
            issue_id.removeprefix(prefix)
            for domain, issue_id in self.issue_registry.issues
            if domain == SPOOK_DOMAIN and issue_id.startswith(prefix)
        )
