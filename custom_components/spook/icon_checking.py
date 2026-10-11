"""Spook - Your homie. Telling an icon the frontend has from one it does not.

An `mdi:` icon is drawn from a list of names the frontend ships with, read
from files of its own. A name that is not on that list is drawn as nothing at
all: no error, no log, just an empty spot where the icon should be.

The list is read from the frontend Home Assistant has installed, so it is
always the one the browser gets, at the version it gets. Removed icons stay
on that list while the frontend still draws them, so being on it is exactly
being drawn.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import importlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from homeassistant.const import CONF_ACTION, CONF_ENABLED, CONF_SERVICE
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.util.hass_dict import HassKey

from .attribute_checking import suggest_name
from .const import LOGGER

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Iterable, Iterator

    from homeassistant.core import HomeAssistant

# The only prefix judged. The frontend reads `hass`, `hassio` and `hademo`
# from the same list, but those are older names Spook leaves alone. Every
# other prefix is a set of icons somebody added, which Spook has no list of.
MDI_PREFIX: Final = "mdi"

# Logos the frontend draws under the MDI prefix from its own code, not from
# the list. Kept in sync with `CUSTOM_ICONS` in its `ha-icon.ts`.
_FRONTEND_OWN_ICONS: Final = frozenset(
    {"esphome", "home-assistant", "matter", "mqtt", "music-assistant"}
)

# What a template or a card's own variables turn into is not known until they
# run. Jinja, button-card's `[[[ ]]]`, decluttering-card's `[[ ]]` and
# config-template-card's `${ }`.
_TEMPLATE_MARKERS: Final = ("{{", "{%", "{#", "[[", "${")

# How an action's description says a field takes an icon.
_ICON_SELECTOR: Final = "icon"

# Where a step keeps what it hands to its action. `data_template` is the old
# name, still read by Home Assistant.
_ACTION_DATA_KEYS: Final = ("data", "data_template")

DATA_MDI_ICONS: HassKey[asyncio.Future[MdiIcons | None]] = HassKey("spook_mdi_icons")


@dataclass(frozen=True, slots=True)
class MdiIcons:
    """The Material Design Icons the installed frontend draws."""

    version: str
    names: frozenset[str]

    # Worked out once per name. Looking for the closest of thousands of names
    # takes a moment, and the same mistake shows up round after round.
    suggestions: dict[str, str | None] = field(default_factory=dict, compare=False)

    def unknown_name(self, icon: Any) -> str | None:
        """Return the name of an `mdi:` icon the frontend does not draw.

        Read the way the frontend reads it: split on colons, the first part
        the prefix and the second the name. Anything after a second colon is
        dropped, so `mdi:lightbulb:old` is drawn as a lightbulb.
        """
        if not isinstance(icon, str) or any(
            marker in icon for marker in _TEMPLATE_MARKERS
        ):
            return None

        prefix, _, rest = icon.partition(":")
        name = rest.split(":", 1)[0]

        # Without a name the frontend draws nothing, and does not look.
        if prefix != MDI_PREFIX or not name:
            return None

        if name in self.names or name in _FRONTEND_OWN_ICONS:
            return None

        return name

    def describe(self, icon: str) -> str:
        """Return an unknown icon for an issue, with its likely meaning."""
        name = self.unknown_name(icon)
        if name is None or (suggestion := self.suggestions.get(name)) is None:
            return f"`{icon}`"
        return f"`{icon}` (did you mean `{MDI_PREFIX}:{suggestion}`?)"


def _frontend_static_folder() -> Path | None:
    """Return the static folder of the installed frontend, if there is one."""
    try:
        frontend = importlib.import_module("hass_frontend")
        return Path(frontend.where()) / "static"
    except ImportError, AttributeError, TypeError:
        return None


def _load_mdi_icons() -> MdiIcons | None:
    """Read the icons the installed frontend draws, or None if it cannot say.

    A frontend built for development leaves the list out, and an incomplete
    list would turn every icon it misses into a finding. So anything less
    than all of it means nothing is judged.
    """
    if (static := _frontend_static_folder()) is None:
        LOGGER.debug("Spook found no frontend, so icons are not checked")
        return None

    folder = static / "mdi"
    names: set[str] = set()
    try:
        metadata = json.loads((folder / "iconMetadata.json").read_text("utf-8"))
        version = str(metadata["version"])
        for part in metadata["parts"]:
            chunk = json.loads((folder / f"{part['file']}.json").read_text("utf-8"))
            if not isinstance(chunk, dict):
                return None
            names.update(chunk)
    except OSError, ValueError, KeyError, TypeError:
        LOGGER.debug("Spook could not read the frontend icons, so none are checked")
        return None

    if not names:
        return None

    return MdiIcons(version=version, names=frozenset(names))


async def async_get_mdi_icons(hass: HomeAssistant) -> MdiIcons | None:
    """Return the icons the installed frontend draws, or None if unknown.

    Read once, in the executor: it is a few dozen files. The frontend cannot
    change without a restart, so neither can the answer.
    """
    if (loading := hass.data.get(DATA_MDI_ICONS)) is None:
        loading = hass.async_add_executor_job(_load_mdi_icons)
        hass.data[DATA_MDI_ICONS] = loading
    return await loading


def _suggestions(names: Iterable[str], known: frozenset[str]) -> dict[str, str | None]:
    """Return the closest known name for each, when it is near certain."""
    return {name: suggest_name(name, known) for name in names}


async def async_icon_fields(hass: HomeAssistant) -> dict[str, frozenset[str]]:
    """Return, per action, the fields that take an icon.

    Only what an action says takes one, with an icon selector in its
    description. A field that is merely called `icon` can be anything: the
    notifications of `html5` and `ntfy` take a picture's address there.
    """
    descriptions = await async_get_all_descriptions(hass)
    return {
        f"{domain}.{service}": fields
        for domain, services in descriptions.items()
        for service, description in services.items()
        if (fields := frozenset(_icon_fields(description.get("fields") or {})))
    }


def _icon_fields(fields: Mapping[str, Any]) -> Iterator[str]:
    """Yield the fields with an icon selector, from inside sections too."""
    for name, spec in fields.items():
        if not isinstance(spec, Mapping):
            continue
        if isinstance(nested := spec.get("fields"), Mapping):
            yield from _icon_fields(nested)
        elif isinstance(selector := spec.get("selector"), Mapping) and (
            _ICON_SELECTOR in selector
        ):
            yield name


def icons_in_actions(
    config: Any, icon_fields: Mapping[str, frozenset[str]]
) -> set[str]:
    """Return the icons that the actions in a configuration hand over.

    Walks the configuration as written, so every kind of nested block is
    covered without naming them. A step that is turned off never runs, so
    neither does anything inside it.
    """
    icons: set[str] = set()

    if isinstance(config, list):
        for item in config:
            icons |= icons_in_actions(item, icon_fields)
        return icons

    if not isinstance(config, Mapping) or config.get(CONF_ENABLED) is False:
        return icons

    action = config.get(CONF_ACTION, config.get(CONF_SERVICE))
    for key in _ACTION_DATA_KEYS:
        if not isinstance(action, str) or not isinstance(
            data := config.get(key), Mapping
        ):
            continue
        # Lowered, the way Home Assistant reads an action name.
        for field_name in icon_fields.get(action.lower(), ()):
            if isinstance(icon := data.get(field_name), str):
                icons.add(icon)

    for key, value in config.items():
        if key not in _ACTION_DATA_KEYS:
            icons |= icons_in_actions(value, icon_fields)

    return icons


async def async_suggest(
    hass: HomeAssistant, icons: MdiIcons, found: Iterable[str]
) -> None:
    """Work out what each unknown icon most likely meant, before describing it.

    In the executor: comparing a name against every icon takes long enough to
    be noticed on the event loop, and a round can have a few.
    """
    names = {
        name
        for icon in found
        if (name := icons.unknown_name(icon)) is not None
        and name not in icons.suggestions
    }
    if not names:
        return

    icons.suggestions.update(
        await hass.async_add_executor_job(_suggestions, names, icons.names)
    )
