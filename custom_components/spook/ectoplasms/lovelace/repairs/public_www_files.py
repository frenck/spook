"""Spook - Your homie."""

from __future__ import annotations

from bisect import insort
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from homeassistant.components.frontend import DATA_THEMES
from homeassistant.components.lovelace import DOMAIN
from homeassistant.components.lovelace.const import ConfigNotFound
from homeassistant.const import EVENT_LOVELACE_UPDATED, EVENT_THEMES_UPDATED
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from ....const import DOMAIN as SPOOK_DOMAIN, LOGGER
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )

_LOCAL_PREFIX = "/local/"

# Where the Marketplace, and HACS before it, installs dashboard cards.
_MARKETPLACE_FOLDER = "community"

# What the frontend loads as code. A folder holding any of it is a card or
# a theme somebody put up on purpose, images and all.
_FRONTEND_CODE = frozenset({".cjs", ".css", ".js", ".map", ".mjs"})

# Files straight in `www`. No folder can be called this.
_ROOT = "."

# Enough to recognise what it is, without turning the issue into a listing.
_SHOWN = 10


def _collect_local_links(node: Any, found: set[str]) -> None:
    """Collect every text in this config that links into `www`.

    Cards keep their images under all sorts of keys, custom cards most of all,
    so every string is looked at rather than a list of known keys. The text
    is kept whole: where a link ends cannot be told from the outside, as a
    file may be called `plan (1).png`. A file is in use when its own link is
    somewhere in there, written out or encoded the way a URL is.
    """
    if isinstance(node, str):
        if _LOCAL_PREFIX in node:
            found.update((node, unquote(node)))
    elif isinstance(node, dict):
        for value in node.values():
            _collect_local_links(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_local_links(value, found)


def _is_code(path: Path) -> bool:
    """Return whether the frontend loads this file as code."""
    return path.suffix.lower() in _FRONTEND_CODE


def _is_hidden(path: Path, www: Path) -> bool:
    """Return whether a file is, or sits in, something hidden."""
    return any(part.startswith(".") for part in path.relative_to(www).parts)


@dataclass(slots=True)
class _Found:
    """The files found in one folder: how many, and the first few by name.

    Not all of them. An integration that keeps writing here can leave tens of
    thousands behind, and only a handful are shown.
    """

    count: int = 0
    first: list[str] = field(default_factory=list)

    def add(self, file: str) -> None:
        """Count a file, and keep it when it is among the first by name."""
        self.count += 1
        if len(self.first) == _SHOWN and file > self.first[-1]:
            return

        insort(self.first, file)
        del self.first[_SHOWN:]


def _found_among(
    paths: Iterable[Path], www: Path, links: str, *, code_clears: bool
) -> _Found | None:
    """Return the files among these that nobody seems to have put up on purpose.

    Nothing at all for a folder that holds code: that is a card or a theme,
    images and all.
    """
    found = _Found()
    for path in paths:
        if not path.is_file() or _is_hidden(path, www):
            continue

        if _is_code(path):
            if code_clears:
                return None
            continue

        file = path.relative_to(www).as_posix()
        if f"{_LOCAL_PREFIX}{file}" not in links:
            found.add(file)

    return found if found.count else None


def _public_files(www: Path, links: str) -> dict[str, _Found]:
    """Return the files nobody seems to have put up on purpose, by folder."""
    if not www.is_dir():
        return {}

    entries = [
        entry
        for entry in www.iterdir()
        if not entry.name.startswith(".") and entry.name != _MARKETPLACE_FOLDER
    ]

    # Files straight in `www` are judged one by one: a card next to them says
    # nothing about them.
    in_folders = {_ROOT: _found_among(entries, www, links, code_clears=False)}
    for entry in entries:
        if entry.is_dir() and not entry.is_symlink():
            in_folders[entry.name] = _found_among(
                entry.rglob("*"), www, links, code_clears=True
            )

    return {folder: found for folder, found in in_folders.items() if found}


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds files in `www` that anyone can download.

    Home Assistant serves the `www` folder at `/local/` without asking anyone
    to log in, as browsers load cards and images from it with a plain link.
    That is fine for those, but integrations store camera snapshots, print
    previews and the like there too, often without the user knowing.
    """

    domain = DOMAIN
    repair = "lovelace_public_www_files"
    # Not when a component loads: that happens hundreds of times while Home
    # Assistant starts, and each look walks all of `www`. It is looked at
    # once when Spook starts anyway.
    inspect_events = {
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
        for key, dashboard in list(self._dashboards.items()):
            # The old default dashboard, a leftover nobody can open. #1593.
            if key is None and "lovelace" in self._dashboards:
                continue
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
            _collect_local_links(config, in_use)
        _collect_local_links(self.hass.data.get(DATA_THEMES, {}), in_use)

        public = await self.hass.async_add_executor_job(
            _public_files, Path(self.hass.config.path("www")), "\n".join(in_use)
        )

        # Keyed to the folder and not to the files in it: an integration that
        # keeps adding files would otherwise bring an ignored issue back with
        # every one of them.
        for folder, found in public.items():
            url = _LOCAL_PREFIX if folder == _ROOT else f"{_LOCAL_PREFIX}{folder}/"
            self.async_create_issue(
                issue_id=folder,
                translation_placeholders={
                    "folder": url,
                    "count": str(found.count),
                    "files": "\n".join(
                        f"- `{_LOCAL_PREFIX}{file}`" for file in found.first
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
