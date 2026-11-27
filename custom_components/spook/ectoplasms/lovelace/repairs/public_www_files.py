"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from bisect import insort
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
import re
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from homeassistant.components.frontend import DATA_THEMES
from homeassistant.components.lovelace import DOMAIN
from homeassistant.components.lovelace.const import ConfigNotFound
from homeassistant.const import EVENT_LOVELACE_UPDATED, EVENT_THEMES_UPDATED
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import DATA_INSTANCES

from ....const import LOGGER, YIELD_AFTER
from ....repairs import AbstractSpookRepair, CouldNotLook

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

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

# Only automations and scripts keep the configuration they were made from.
_CONFIGURED_DOMAINS = ("automation", "script")

# A link that something fills in when it runs: a Jinja template, a JavaScript
# one, or a quoted start that a template joins the rest onto, as in
# `'/local/icons/' ~ kind`. Read up to the first space, so a template elsewhere
# in the same text, like the value in a notification, is not taken for a part
# of the link. And no further than a `?` or `#`: what is filled in behind
# those, like a version to get around the cache, does not change which file
# it is.
_BUILT_LINK = re.compile(r"""/local/([^\s'"?#]*?)(?:\{\{|\{%|\$\{|['"]\s*[~+])""")


def _collect_local_links(node: Any, found: set[str]) -> None:
    """Collect every text in this config that links into `www`.

    Cards keep their images under all sorts of keys, custom cards most of all,
    so every string is looked at rather than a list of known keys. The same
    goes for state attributes and what automations and scripts send along.
    The text is kept whole: where a link ends cannot be told from the outside,
    as a file may be called `plan (1).png`. A file is in use when its own link
    is somewhere in there, written out or encoded the way a URL is. Decoding
    comes later, and once: here the text is kept as it was written.
    """
    if isinstance(node, str):
        if _LOCAL_PREFIX in node:
            found.add(node)
    elif isinstance(node, Mapping):
        for value in node.values():
            _collect_local_links(value, found)
    elif isinstance(node, (list, tuple, set)):
        for value in node:
            _collect_local_links(value, found)


def _folders_built_into(links: Iterable[str]) -> set[str] | None:
    """Return the folders that links filled in when they run point into.

    Which file `/local/icons/{{ kind }}.png` ends up at is only known when it
    runs, so every file in `icons` may be the one. When the folder itself is
    filled in, or the file straight in `www`, any file may be: then this
    returns nothing at all, and nothing can be said about any of them.
    """
    folders: set[str] = set()
    for link in links:
        for match in _BUILT_LINK.finditer(link):
            folder, slash, _ = match[1].partition("/")
            if not slash:
                return None

            # The folder is called what the link decodes to: `my%20icons`
            # in a link is `my icons` on disk.
            folders.add(unquote(folder))

    return folders


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


def _public_files(www: Path, links: str, folders_in_use: set[str]) -> dict[str, _Found]:
    """Return the files nobody seems to have put up on purpose, by folder."""
    if not www.is_dir():
        return {}

    entries = [
        entry
        for entry in www.iterdir()
        if not entry.name.startswith(".")
        and entry.name != _MARKETPLACE_FOLDER
        and entry.name not in folders_in_use
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

        # Collect what dashboards and themes link to, and what runs: states,
        # automations, scripts and config entries. Those files are left alone.
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
            except HomeAssistantError as err:
                # Without its links, files it shows would be reported wrongly.
                LOGGER.warning(
                    "Spook could not read dashboard %s, so it skipped looking "
                    "for public files in www",
                    dashboard.url_path or "lovelace",
                )
                msg = "A dashboard could not be read, so what it links to is not known"
                raise CouldNotLook(msg) from err
            _collect_local_links(config, in_use)
        _collect_local_links(self.hass.data.get(DATA_THEMES, {}), in_use)
        await self._async_collect_running_links(in_use)

        # Issues raised before go as well. Unlike a dashboard that cannot be
        # read, a template is here to stay.
        if (folders_in_use := _folders_built_into(in_use)) is None:
            LOGGER.debug(
                "Spook found a link into www that a template fills in, "
                "so any file there may be in use"
            )
            return

        public = await self.hass.async_add_executor_job(
            _public_files,
            Path(self.hass.config.path("www")),
            # As written and decoded both: a link may spell a file's name out,
            # or encode it the way a URL does.
            "\n".join(in_use | {unquote(link) for link in in_use}),
            folders_in_use,
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

    async def _async_collect_running_links(self, found: set[str]) -> None:
        """Collect what states, automations, scripts and config entries link to.

        A picture set with `customize:` or by an integration ends up in a
        state, a notification image in an automation, a picture of a helper
        made in the UI in its config entry. Thousands of states on a large
        installation, so the event loop gets a turn in between.
        """
        slice_started = time.monotonic()
        for config in self._running_configs():
            _collect_local_links(config, found)
            if time.monotonic() - slice_started > YIELD_AFTER:
                await asyncio.sleep(0)
                slice_started = time.monotonic()

    def _running_configs(self) -> Iterator[Any]:
        """Yield the states, configurations and entry contents to look at."""
        for state in self.hass.states.async_all():
            yield state.state
            yield state.attributes

        for domain in _CONFIGURED_DOMAINS:
            if component := self.hass.data.get(DATA_INSTANCES, {}).get(domain):
                # A copy: the event loop gets turns in between, and a reload
                # in one of them would change what is being walked.
                for entity in list(component.entities):
                    yield getattr(entity, "raw_config", None)

        for entry in self.hass.config_entries.async_entries():
            yield entry.data
            yield entry.options
