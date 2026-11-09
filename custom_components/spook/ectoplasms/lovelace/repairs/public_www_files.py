"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_LOVELACE_UPDATED

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ..dashboards import async_dashboard_configs

if TYPE_CHECKING:
    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )

_LOCAL_PREFIX = "/local/"

# Where HACS puts the frontend plugins it installs, served as `/hacsfiles/`.
_HACS_FOLDER = "community"

# What the frontend loads as code. A folder holding any of it is a card or
# a theme somebody put up on purpose, images and all.
_FRONTEND_CODE = frozenset({".cjs", ".css", ".js", ".map", ".mjs"})

# The issue for files straight in `www`, rather than in a folder of their own.
_ROOT = "www"

# Enough to recognise what it is, without turning the issue into a listing.
_SHOWN = 10


def _collect_local_paths(node: Any, found: set[str]) -> None:
    """Collect the `www` paths a dashboard points at, wherever it does so.

    Cards keep their images under all sorts of keys, custom cards most of all,
    so every string is looked at rather than a list of known keys.
    """
    if isinstance(node, str):
        if _LOCAL_PREFIX in node:
            path = node.split(_LOCAL_PREFIX, 1)[1].split("?", 1)[0]
            found.add(unquote(path))
    elif isinstance(node, dict):
        for value in node.values():
            _collect_local_paths(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_local_paths(value, found)


def _is_hidden(path: Path, www: Path) -> bool:
    """Return whether a file is, or sits in, something hidden."""
    return any(part.startswith(".") for part in path.relative_to(www).parts)


def _public_files(www: Path, in_use: set[str]) -> dict[str, list[str]]:
    """Return the files nobody seems to have put up on purpose, by folder."""
    found: dict[str, list[str]] = {}
    if not www.is_dir():
        return found

    for entry in www.iterdir():
        if entry.name.startswith(".") or entry.name == _HACS_FOLDER:
            continue

        if entry.is_file():
            folder, files = _ROOT, [entry]
        elif entry.is_dir() and not entry.is_symlink():
            files = [
                path
                for path in entry.rglob("*")
                if path.is_file() and not _is_hidden(path, www)
            ]
            if any(path.suffix.lower() in _FRONTEND_CODE for path in files):
                continue
            folder = entry.name
        else:
            continue

        for path in files:
            relative = path.relative_to(www).as_posix()
            if path.suffix.lower() in _FRONTEND_CODE or relative in in_use:
                continue
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

        in_use: set[str] = set()
        async for _, _, config in async_dashboard_configs(self._dashboards):
            _collect_local_paths(config, in_use)

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
