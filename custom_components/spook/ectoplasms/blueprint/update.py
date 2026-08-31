"""Spook - Your homie. Updates for blueprints that came from somewhere."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import timedelta
import hashlib
import json
import os
import random
import re
import shutil
from typing import TYPE_CHECKING, Any, NamedTuple

import aiohttp
from annotatedyaml.objects import Input
import voluptuous as vol

from homeassistant.components import blueprint
from homeassistant.components.automation import (
    automations_with_blueprint,
    config as automation_config,
)
from homeassistant.components.blueprint import BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.const import (
    CONF_BLUEPRINT,
    CONF_HOMEASSISTANT,
    CONF_MIN_VERSION,
    CONF_SOURCE_URL,
)
from homeassistant.components.blueprint.importer import fetch_blueprint_from_url
from homeassistant.components.script import (
    config as script_config,
    scripts_with_blueprint,
)
from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_ON,
    Platform,
)
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util, yaml as yaml_util

from ...const import DOMAIN, LOGGER
from ...entity import SpookEntity, SpookEntityDescription
from ...listeners import async_listen_once_tracked

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime
    from pathlib import Path

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class _UsesBlueprints:
    """What has to be to hand before Spook will follow a domain's blueprints.

    Its users, so they can be asked what they supply, and the same validation
    a reload puts them through, so an update can be tried on them before
    anything is written.
    """

    users: Callable[[HomeAssistant, str], list[str]]
    validate: Callable[
        [HomeAssistant, str, dict[str, Any]],
        Awaitable[Any],
    ]

    one: str
    """What one of them is called, for a sentence about it."""

    many: str
    """And what more than one of them are called."""

    edit_url: str
    """Where to edit one, given its unique ID."""

    dashboard_url: str
    """And where to send somebody whose own has no unique ID to link to."""


# Which is why it is these two and not template blueprints as well. Without
# both halves there is no telling whether an update would leave something
# unable to load, and an install button that cannot promise that is worse than
# no button at all.
_USES_BLUEPRINTS: dict[str, _UsesBlueprints] = {
    "automation": _UsesBlueprints(
        users=automations_with_blueprint,
        validate=automation_config.async_validate_config_item,
        one="automation",
        many="automations",
        edit_url="/config/automation/edit/{unique_id}",
        dashboard_url="/config/automation/dashboard",
    ),
    "script": _UsesBlueprints(
        users=scripts_with_blueprint,
        validate=script_config.async_validate_config_item,
        one="script",
        many="scripts",
        edit_url="/config/script/edit/{unique_id}",
        dashboard_url="/config/script/dashboard",
    ),
}

# The folder Home Assistant fills with its own example blueprints. All three of
# them carry a source URL pointing at core's dev branch, so following them would
# put an update on every installation there is, for something nobody imported,
# out of a branch that is not the one they are running.
_HOME_ASSISTANTS_OWN = f"homeassistant{os.sep}"

# Every one of these is a request to somebody else's server, and the community
# forum and GitHub between them host nearly all of it. Restarts cluster after a
# release, so the first round waits a random while rather than joining the
# stampede, and every round after it picks its own moment a day or so on rather
# than keeping to the hour the first one happened to land on.
_FIRST_CHECK_WINDOW = (timedelta(minutes=5), timedelta(minutes=30))
_CHECK_INTERVAL = timedelta(hours=24)
_SPREAD = timedelta(hours=4)

_FETCH_TIMEOUT = 30

# What goes in the dialog before somebody presses install. Home Assistant
# renders `ha-alert` in release notes, which Matter and ZHA both lean on to put
# a warning in front of a firmware update. Same idea here.
_NO_PROMISES = (
    "<ha-alert alert-type='warning'>"
    "Blueprints carry no changelog. What is below is Spook comparing the two "
    "files, not the author saying what they did, and nothing promises an "
    "update still fits the automations you built on it: inputs get renamed, "
    "behaviour gets rethought. Read the source before you install it."
    "</ha-alert>"
)

_WOULD_NOT_RUN = (
    "<ha-alert alert-type='error'>"
    "This version says it needs a newer Home Assistant than the one you are "
    "running, so Spook will not install it."
    "</ha-alert>"
)

# Deliberately says nothing about why. There are three reasons a thing can end
# up on that list and the line next to each one gives its own; a heading that
# names only the commonest of them sends people off fixing the wrong thing.
_WOULD_BE_REFUSED = (
    "<ha-alert alert-type='error'>"
    "Spook will not install this one. What is listed below would stop loading "
    "the moment it is written, and the version it does work with is gone by "
    "then. Put those right first, or import it yourself from the blueprint "
    "page if you would rather sort them out afterwards."
    "</ha-alert>"
)


# Sortable, and without the colons a time usually carries: those cost you the
# file the moment the configuration folder is reached over Samba or sits on a
# Windows share. Home Assistant's own backups avoid them the same way.
_WHEN = "%Y-%m-%d_%H%M%S"

# What a copy of a blueprint is called: the file's own name, when it was put
# aside, and an extension that is deliberately not .yaml. Home Assistant globs
# `**/*.yaml` through the blueprint folders, so a copy ending in .yaml would
# come back as a blueprint of its own, complete with an update entity.
_COPY = re.compile(r"\A(?P<of>.+)\.\d{4}-\d{2}-\d{2}_\d{6}\.bak\Z")

# Kept per blueprint. Enough to go back past an update that looked fine at the
# time, few enough that the folder stays readable to somebody who opens it.
_KEEP_COPIES = 3

_WHAT_DIFFERS = "**Compared with the copy you have:**\n"
_ASKS_FOR = "**It now asks for Home Assistant "

_CANNOT_SAY_WHAT_DIFFERS = (
    "<ha-alert alert-type='info'>"
    "Spook could not read the copy you have just now, so it cannot say what "
    "this changes."
    "</ha-alert>"
)

# Settings named before it turns into a wall. Past a few, what somebody needs
# to know is how many there are, not what every one of them is called.
_HOW_MANY_TO_NAME = 3

# The keys at the top of a blueprint that say what it does. Grouped, because
# "the triggers changed" and "the actions changed" are the same news to
# somebody deciding whether to install this.
_WHAT_IT_DOES = {
    "trigger": "When it runs",
    "triggers": "When it runs",
    "condition": "The conditions on it",
    "conditions": "The conditions on it",
    "action": "What it does",
    "actions": "What it does",
    "sequence": "What it does",
    "variables": "The variables in it",
    "fields": "The fields it takes",
    "mode": "How it handles overlapping runs",
    "max": "How it handles overlapping runs",
    "max_exceeded": "How it handles overlapping runs",
}

# And the ones that only say what it is called. A blueprint whose description
# changed and nothing else is worth saying out loud precisely because it means
# somebody can stop reading.
_WHAT_IT_IS_CALLED = {
    "name": "Its name",
    "description": "Its description",
    "author": "Who it says wrote it",
    "domain": "The kind of thing it builds",
}


def _keep_a_copy(file: Path) -> None:
    """Put a copy of a blueprint beside it, and let go of the oldest.

    Runs in the executor: all of it touches the disk.
    """
    if not file.exists():
        # Nothing to keep. The install is about to write it fresh, which is
        # the best that can be done for a file that is not there.
        return

    when = dt_util.now().strftime(_WHEN)
    shutil.copy2(file, file.with_name(f"{file.name}.{when}.bak"))

    for old in _copies_of(file)[_KEEP_COPIES:]:
        old.unlink(missing_ok=True)


def _copies_of(file: Path) -> list[Path]:
    """Return the copies of a blueprint, newest first.

    Sorted by name, which is by time, because that is what the stamp is for.

    Matched on the whole shape rather than the leading part of the name. A
    blueprint called `motion.yaml.old.yaml` would otherwise have its copies
    counted as copies of `motion.yaml`, and thrown away as somebody else's.
    """
    copies = [
        candidate
        for candidate in file.parent.iterdir()
        if (match := _COPY.match(candidate.name)) is not None
        and match["of"] == file.name
    ]

    return sorted(copies, reverse=True)


def _unique_id(blueprint_domain: str, blueprint_path: str) -> str:
    """Return the unique ID of the entity following a blueprint."""
    return f"blueprint_{blueprint_domain}_{blueprint_path}"


def _blueprint_behind(unique_id: str) -> tuple[str, str] | None:
    """Return the blueprint a unique ID of ours is about, if it is one.

    Matched against the domains themselves rather than split on the
    separator, because a blueprint path is free to hold underscores of its
    own and a domain is not.
    """
    for blueprint_domain in _USES_BLUEPRINTS:
        prefix = _unique_id(blueprint_domain, "")
        if unique_id.startswith(prefix):
            return blueprint_domain, unique_id.removeprefix(prefix)

    return None


class _Found(NamedTuple):
    """What a look at the blueprint folders turned up."""

    files: dict[tuple[str, str], Path]
    """The file behind every blueprint Home Assistant could load."""

    listed: set[tuple[str, str]]
    """Every blueprint Home Assistant named, loadable or not."""

    domains: set[str]
    """The domains that were there to be asked. Absence is not emptiness."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an update entity for every blueprint that came from a URL."""
    await _BlueprintUpdates(hass, entry, async_add_entities).async_start()


@dataclass(frozen=True, kw_only=True)
class _OnDisk:
    """What a blueprint file says, as of just now.

    No source URL means it was read perfectly well and is not being followed,
    which is a different answer from not having been able to read it at all.
    """

    name: str
    source_url: str | None
    fingerprint: str


def _normalize(raw: str) -> blueprint.Blueprint | None:
    """Return a blueprint parsed the same way on both sides of a comparison.

    Deliberately not through the domain's own schema. That one rewrites the
    older spellings, `trigger` into `triggers` and the rest of it, and only the
    copy Home Assistant has loaded ever goes through it. Measuring that against
    a freshly fetched one would call every blueprint written before those names
    changed out of date, for ever.
    """
    try:
        return blueprint.Blueprint(yaml_util.parse_yaml(raw), schema=BLUEPRINT_SCHEMA)
    except HomeAssistantError:
        return None


def _canonical(value: Any) -> Any:
    """Return a form in which no two different things can look the same.

    Every value carries what kind of thing it is. Without that, a mapping
    somebody wrote by hand could serialize exactly like an `!input`, and
    swapping one for the other changes what a blueprint does while leaving the
    fingerprint alone.

    Mappings become ordered lists of pairs rather than objects, which keeps
    their order in the hash. That order is not decoration: a `variables:`
    block is rendered one entry at a time with earlier results available to
    later ones, so `{a: 1, b: "{{ a }}"}` and the same two the other way round
    are different scripts.

    Keys go through here too. YAML hands back real integers, booleans and
    floats as keys, so `{1: a}` and `{"1": a}` are different mappings and
    stringifying both would have hidden the difference.

    Anything JSON cannot hold is named by its type and written out as text. An
    unquoted date in a blueprint arrives as a `datetime.date`, and that used
    to take the whole round down with a `TypeError`.

    The loader's own string and mapping classes go too. They carry the line
    they came from, which says nothing about what the blueprint does.
    """
    if isinstance(value, Input):
        return ["input", str(value.name)]
    if isinstance(value, Mapping):
        return [
            "map",
            [[_canonical(key), _canonical(item)] for key, item in value.items()],
        ]
    if isinstance(value, (list, tuple)):
        return ["seq", [_canonical(item) for item in value]]
    if isinstance(value, (set, frozenset)):
        # A set carries no order of its own, and Python's iteration order for
        # one is not stable between runs, so the members are sorted once
        # encoded. `!!set` is rare in a blueprint but it parses.
        return ["set", sorted(json.dumps(_canonical(item)) for item in value)]

    return _canonical_scalar(value)


def _canonical_scalar(value: Any) -> Any:
    """Return the encoded form of something that holds nothing else."""
    if isinstance(value, str):
        return ["str", str(value)]
    if value is None or isinstance(value, (bool, int, float)):
        return ["value", value]

    # A date, a datetime, a `!!binary`: things YAML produces that JSON cannot
    # take. Without this the whole round died on a `TypeError` from a blueprint
    # holding an unquoted date. Named by their type so two different kinds
    # cannot look alike, and written out as text because that is all JSON can
    # hold.
    return [f"other:{type(value).__name__}", str(value)]


def _compared(item: blueprint.Blueprint) -> dict[str, Any]:
    """Return the part of a blueprint that two versions are judged on.

    Which is all of it bar the source URL. That one is put in by whoever
    imported the blueprint rather than by its author, it is the address this
    was fetched from in the first place, and an author who moves their
    blueprint has not changed it.
    """
    data = dict(item.data)

    if isinstance(metadata := data.get(CONF_BLUEPRINT), Mapping):
        metadata = dict(metadata)
        metadata.pop(CONF_SOURCE_URL, None)
        data[CONF_BLUEPRINT] = metadata

    return data


@dataclass(frozen=True, kw_only=True)
class _Changes:
    """What is different between two versions of a blueprint.

    In terms somebody deciding whether to install it can act on, rather than
    the keys of the file it came out of. Nobody has ever wanted to be told
    that `blueprint.input.light_target` is gone.
    """

    settings_new: list[str]
    settings_gone: list[str]
    settings_changed: list[str]

    doing: set[str]
    """What it does, in the words of `_WHAT_IT_DOES`."""

    calling: set[str]
    """What it is called, in the words of `_WHAT_IT_IS_CALLED`."""

    needs: str | None
    """A Home Assistant version it now asks for and did not before."""

    rearranged: bool
    """Nothing above, and still not the same file."""

    def __bool__(self) -> bool:
        """Return whether anything at all was found."""
        return bool(
            self.settings_new
            or self.settings_gone
            or self.settings_changed
            or self.doing
            or self.calling
            or self.needs
            or self.rearranged,
        )


def _called(key: str, definition: Any) -> str:
    """Return what an input is called, as its author wrote it.

    Falling back to the key, which is what somebody who never gave it a name
    would recognise it by anyway.
    """
    if isinstance(definition, Mapping) and isinstance(
        name := definition.get(CONF_NAME),
        str,
    ):
        return name

    return key


def _spelled_out(settings: list[tuple[str, str]], labels: list[str]) -> list[str]:
    """Return what to call each setting, unambiguously."""
    return [
        label if labels.count(label) == 1 else f"{label} (`{key}`)"
        for label, key in settings
    ]


class _Settings(NamedTuple):
    """The settings that are new, gone and changed between two versions."""

    new: list[str]
    gone: list[str]
    changed: list[str]


def _settings_apart(
    before: blueprint.Blueprint,
    after: blueprint.Blueprint,
) -> _Settings:
    """Return how the settings somebody fills in have moved.

    Read through Home Assistant's own flattened view, so an input inside a
    section counts as an input rather than as part of the section.
    """
    here, there = before.inputs, after.inputs

    gone = [(_called(key, here[key]), key) for key in here if key not in there]
    new = [(_called(key, there[key]), key) for key in there if key not in here]
    changed = [
        (_called(key, there[key]), key)
        for key in here
        if key in there and _canonical(here[key]) != _canonical(there[key])
    ]

    # An author who renames the key and keeps the label leaves two settings
    # reading the same, which is the one rename that says nothing while
    # breaking everything: whatever somebody set is stored under the old key
    # and the new version never looks there. So the key comes along whenever a
    # label alone would not tell them apart.
    labels = [label for label, _ in [*gone, *new, *changed]]

    return _Settings(
        new=_spelled_out(new, labels),
        gone=_spelled_out(gone, labels),
        changed=_spelled_out(changed, labels),
    )


def _doing_apart(was: dict[str, Any], now: dict[str, Any]) -> set[str]:
    """Return what a blueprint does differently, in words."""
    doing: set[str] = set()

    for key in dict.fromkeys([*was, *now]):
        if key == CONF_BLUEPRINT:
            continue

        if _canonical(was.get(key)) != _canonical(now.get(key)):
            doing.add(_WHAT_IT_DOES.get(str(key), "Something else in it"))

    return doing


def _calling_apart(
    before: blueprint.Blueprint,
    after: blueprint.Blueprint,
) -> set[str]:
    """Return what a blueprint calls itself differently, in words."""
    return {
        words
        for key, words in _WHAT_IT_IS_CALLED.items()
        if _canonical(before.metadata.get(key)) != _canonical(after.metadata.get(key))
    }


def _needs_apart(
    before: blueprint.Blueprint,
    after: blueprint.Blueprint,
) -> str | None:
    """Return a Home Assistant version a blueprint now asks for and did not.

    An empty string for one that asks for something unreadable, which is still
    worth saying: it did not ask for anything before.
    """
    asked = after.metadata.get(CONF_HOMEASSISTANT)

    if _canonical(before.metadata.get(CONF_HOMEASSISTANT)) == _canonical(asked):
        return None

    return str(asked.get(CONF_MIN_VERSION)) if isinstance(asked, Mapping) else ""


def _changes(before: blueprint.Blueprint, after: blueprint.Blueprint) -> _Changes:
    """Return what is different between two versions of a blueprint.

    Measured through the same canonical form the fingerprint is taken of, so
    what gets said and what made the update appear cannot come apart.
    """
    was, now = _compared(before), _compared(after)
    settings = _settings_apart(before, after)

    changes = _Changes(
        settings_new=settings.new,
        settings_gone=settings.gone,
        settings_changed=settings.changed,
        doing=_doing_apart(was, now),
        calling=_calling_apart(before, after),
        needs=_needs_apart(before, after),
        rearranged=False,
    )

    # Everything above agreeing while the files do not means the same things
    # are written in a different order. Which counts: Home Assistant renders
    # some blocks in the order they appear, a `variables:` block among them.
    if changes or _canonical(was) == _canonical(now):
        return changes

    return replace(changes, rearranged=True)


def _named(names: list[str]) -> str:
    """Return a few names, or a count once there are too many to read."""
    if len(names) > _HOW_MANY_TO_NAME:
        return str(len(names))

    return ", ".join(names)


def _in_words(changes: _Changes) -> list[str]:
    """Return what changed, as lines somebody can act on."""
    if changes.rearranged:
        return [
            (
                "The same things, written in a different order. That can still "
                "change what it does: Home Assistant renders some blocks in "
                "the order they appear."
            ),
        ]

    lines: list[str] = []

    if changes.settings_new:
        lines.append(f"**New settings**: {_named(changes.settings_new)}")
    if changes.settings_gone:
        lines.append(f"**Settings taken away**: {_named(changes.settings_gone)}")
    if changes.settings_changed:
        lines.append(f"**Settings changed**: {_named(changes.settings_changed)}")

    if changes.needs is not None:
        asked = changes.needs or "a particular version"
        lines.append(f"{_ASKS_FOR}{asked}** or newer")

    lines.extend(f"{words} **changed**" for words in sorted(changes.doing))
    lines.extend(f"{words} **changed**" for words in sorted(changes.calling))

    return lines


def _fingerprint(item: blueprint.Blueprint) -> str:
    """Return a short hash of what a blueprint says.

    Blueprints carry no version and cannot be given one: the schema for the
    `blueprint:` block turns away keys it does not know, so an author has
    nowhere to put one. That leaves the content itself as the version.

    Taken off the parsed data rather than off the YAML, which was the first way
    round and the wrong one. Hashing `item.yaml()` hashes how Home Assistant
    chose to lay the file out, and that moves for reasons that have nothing to
    do with the blueprint:

    - Whether libyaml is installed. `annotatedyaml` picks `CSafeDumper` when it
      can and falls back to Python's `SafeDumper`, and the two disagree on 5761
      lines of one real blueprint: 596495 bytes against 605097, unicode escaped
      or not, folded differently.
    - Line width and quoting style, which any PyYAML release is free to change.

    The source URL comes out for the same reason. Where a blueprint was fetched
    from is not part of what it does, and Home Assistant writes it into the
    data on the way in, so leaving it in made a trailing slash on the URL look
    like a new version.
    """
    return hashlib.sha256(
        json.dumps(_canonical(_compared(item)), ensure_ascii=True).encode()
    ).hexdigest()[:8]


def _read_one(file: Path) -> blueprint.Blueprint | None:
    """Return the blueprint a file holds, or `None` if it cannot be read.

    The whole of it, rather than the summary `_read_files` keeps. Only ever
    asked for one blueprint at a time, when somebody has the dialog open, so
    holding all of it in memory is nothing: the summary is what is kept for
    every blueprint on the system, all day.
    """
    try:
        raw = file.read_text(encoding="utf-8")
    except OSError:
        return None

    return _normalize(raw)


def _read_files(files: list[Path]) -> list[_OnDisk | None]:
    """Return what each blueprint file says, in the order given.

    Read off the file rather than taken from the copy Home Assistant has in
    memory, because that one is loaded once and then kept. Editing a file does
    not disturb it, so the name and the source URL it holds can be months out
    of date, and taking that URL back out of a file is the way somebody says
    they would rather be left alone.

    `None` for a file that could not be read or made sense of at all, which is
    not the same as one that was read and names no source.
    """
    on_disk: list[_OnDisk | None] = []
    for file in files:
        try:
            raw = file.read_text(encoding="utf-8")
        except OSError:
            on_disk.append(None)
            continue

        if (item := _normalize(raw)) is None:
            on_disk.append(None)
            continue

        on_disk.append(
            _OnDisk(
                name=item.name,
                source_url=item.metadata.get(CONF_SOURCE_URL) or None,
                fingerprint=_fingerprint(item),
            ),
        )

    return on_disk


@dataclass(frozen=True, kw_only=True)
class BlueprintSpookUpdateEntityDescription(
    SpookEntityDescription,
    UpdateEntityDescription,
):
    """Class describing Spook blueprint update entities."""


class _BlueprintUpdates:  # pylint: disable=too-few-public-methods
    """Keeps the update entities in step with the blueprints on disk.

    Blueprints fire no events at all. Nothing announces one arriving or being
    deleted, so the only way to notice is to look, which happens on the same
    round as the checks.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize the manager."""
        self.hass = hass
        self._entry = entry
        self._async_add_entities = async_add_entities
        self._entities: dict[tuple[str, str], BlueprintUpdateEntity] = {}
        self._stopped = False
        self._cancel: CALLBACK_TYPE | None = None

    async def async_start(self) -> None:
        """Begin now, or once Home Assistant is up.

        Nothing is scheduled before then either. Starting up can take longer
        than the wait before the first round, and a round that lands in the
        middle of it looks at blueprint domains that have not finished
        arriving, and goes out to the internet while the house is still
        getting dressed.
        """
        self._entry.async_on_unload(self._stop)

        # Nothing to do with the rounds below. These entities used to sit on a
        # device, and whoever ran that version still has it.
        self._async_forget_the_old_device()

        if self.hass.state is CoreState.running:
            await self._async_begin()
            return

        self._entry.async_on_unload(
            async_listen_once_tracked(
                self.hass,
                EVENT_HOMEASSISTANT_STARTED,
                self._async_started,
            ),
        )

    @callback
    def _stop(self) -> None:
        """Stop looking, and take the round that was coming with it."""
        self._stopped = True

        if self._cancel is not None:
            self._cancel()
            self._cancel = None

    async def _async_started(self, _event: Event[Any]) -> None:
        """Begin once the blueprint domains have registered themselves."""
        await self._async_begin()

    @callback
    def _async_forget_the_old_device(self) -> None:
        """Remove the device these entities used to hang off.

        They had one called "Blueprints", which is what made every row on the
        updates page read the same. Dropping it leaves the device itself behind
        with nothing on it, and a device that is not a device and holds nothing
        is just something to wonder about later.
        """
        device_registry = dr.async_get(self.hass)
        if (
            device := device_registry.async_get_device_by_identifier(
                (DOMAIN, blueprint.DOMAIN),
                self._entry.entry_id,
            )
        ) is None:
            return

        # Taken off the device first. Home Assistant deletes the registration
        # of every entity on a device when the device goes, and both are ours
        # here, so it would. It hands the registration straight back when the
        # same unique ID turns up again, which is later in this same setup, so
        # nothing is lost by letting it happen. The churn is the reason not to:
        # a dozen repairs re-inspect on any entity registry change, and an
        # entity going and coming back gives them nothing to find.
        entity_registry = er.async_get(self.hass)
        for registration in er.async_entries_for_device(
            entity_registry,
            device.id,
            include_disabled_entities=True,
        ):
            entity_registry.async_update_entity(
                registration.entity_id,
                device_id=None,
            )

        LOGGER.debug("Spook is removing the old blueprints device")
        device_registry.async_remove_device(device.id)

    async def _async_begin(self) -> None:
        """Take stock, then arrange to keep looking."""
        await self._async_take_stock()
        self._async_schedule(
            random.uniform(  # noqa: S311
                _FIRST_CHECK_WINDOW[0].total_seconds(),
                _FIRST_CHECK_WINDOW[1].total_seconds(),
            ),
        )

    @callback
    def _async_schedule(self, delay: float) -> None:
        """Arrange the next round, unless there are to be no more."""
        if self._stopped:
            return

        self._cancel = async_call_later(self.hass, delay, self._async_check_all)

    async def _async_take_stock(self) -> None:
        """Match the entities to the blueprints that are on disk."""
        found = await self._async_look()
        on_disk = await self.hass.async_add_executor_job(
            _read_files,
            list(found.files.values()),
        )

        followed: dict[tuple[str, str], _OnDisk] = {}
        unreadable: set[tuple[str, str]] = set()
        for key, said in zip(found.files, on_disk, strict=True):
            if said is None:
                unreadable.add(key)
            elif said.source_url is not None:
                followed[key] = said

        # A file that could not be read this time round says nothing either
        # way, so whatever is already here stays. A file that was read and no
        # longer names a source is somebody asking to be left alone, and that
        # one goes.
        await self._async_forget(set(self._entities) - set(followed) - unreadable)

        self._async_drop_what_is_not_there(found, followed, unreadable)

        added: list[BlueprintUpdateEntity] = []
        for key in sorted(followed):
            if (entity := self._entities.get(key)) is not None:
                entity.async_seen(followed[key])
                continue

            entity = BlueprintUpdateEntity(*key, followed[key])
            self._entities[key] = entity
            added.append(entity)

        if added:
            self._async_add_entities(added)

    async def _async_look(self) -> _Found:
        """Return what the blueprint folders hold.

        Which domains were asked is part of the answer. A domain that has not
        registered itself says nothing about its blueprints, and reading that
        silence as "there are none" is how a tidy-up turns into a clear-out.
        """
        files: dict[tuple[str, str], Path] = {}
        listed: set[tuple[str, str]] = set()
        domain_blueprints: dict[str, blueprint.DomainBlueprints] = self.hass.data.get(
            blueprint.DOMAIN,
            {},
        )

        domains = {domain for domain in domain_blueprints if domain in _USES_BLUEPRINTS}

        for domain, domain_blueprint in sorted(domain_blueprints.items()):
            if domain not in _USES_BLUEPRINTS:
                continue

            for path, item in (await domain_blueprint.async_get_blueprints()).items():
                # Home Assistant's own examples are not somebody's blueprints.
                if path.startswith(_HOME_ASSISTANTS_OWN):
                    continue

                listed.add((domain, path))

                # Failed to load. Named, so it is there, but nothing can be
                # read out of it.
                if not isinstance(item, blueprint.Blueprint):
                    continue

                files[(domain, path)] = domain_blueprint.blueprint_folder / path

        return _Found(files=files, listed=listed, domains=domains)

    @callback
    def _async_drop_what_is_not_there(
        self,
        found: _Found,
        followed: dict[tuple[str, str], _OnDisk],
        unreadable: set[tuple[str, str]],
    ) -> None:
        """Remove registrations left behind by blueprints that have gone.

        Blueprints fire no events, so one deleted while Home Assistant was
        stopped is noticed by nobody. The round that would have caught it
        compares against the entities of this run, and on the first round
        there are none, so the registration sits there for good: an entity in
        the list with nothing behind it and no way to work out why.

        This is that same comparison, put to the registry instead.

        What it will not do is take a registration on a guess. A blueprint can
        be sitting right there and still not be followed, so being followed is
        not the question. Being gone is.
        """
        registry = er.async_get(self.hass)

        # Named but not loadable: broken YAML, most likely mid-edit. It is
        # there, and nothing can be read out of it to say otherwise.
        keep = found.listed - set(found.files)

        # Read, and asked to be left alone or unreadable just now.
        keep |= set(followed) | unreadable

        wanted = {_unique_id(*key) for key in keep}

        for registration in er.async_entries_for_config_entry(
            registry,
            self._entry.entry_id,
        ):
            if registration.domain != Platform.UPDATE:
                continue

            if (behind := _blueprint_behind(registration.unique_id)) is None:
                continue

            # A domain that was not there to be asked. Its blueprints are out
            # of sight rather than gone, and the difference is every
            # registration it has.
            if behind[0] not in found.domains:
                continue

            if registration.unique_id in wanted:
                continue

            LOGGER.debug(
                "Spook is dropping %s, left behind by a blueprint that is gone",
                registration.entity_id,
            )
            registry.async_remove(registration.entity_id)

    async def _async_forget(self, keys: set[tuple[str, str]]) -> None:
        """Drop the entities of blueprints that are no longer being followed."""
        if not keys:
            return

        registry = er.async_get(self.hass)
        for key in keys:
            entity = self._entities.pop(key)
            await entity.async_remove(force_remove=True)

            # Gone for good, so the registration goes with it rather than
            # lingering as something restorable.
            if registry.async_get(entity.entity_id):
                registry.async_remove(entity.entity_id)

    async def _async_check_all(self, _now: datetime | None = None) -> None:
        """Ask every source whether it has moved on since."""
        self._cancel = None

        if self._stopped:
            return

        try:
            await self._async_take_stock()

            # One at a time on purpose. These nearly all go to two hosts, and
            # nothing here is in a hurry.
            for entity in list(self._entities.values()):
                if self._stopped:
                    return

                try:
                    await entity.async_check()
                # One blueprint pointing somewhere strange must not take the
                # rest of the round with it. Everything expected is already
                # dealt with inside; this is for whatever is not.
                # pylint: disable-next=broad-exception-caught
                except Exception:  # noqa: BLE001
                    LOGGER.exception(
                        "Spook fell over checking blueprint %s; "
                        "please report this at "
                        "https://github.com/frenck/spook/issues",
                        entity.blueprint_path,
                    )
        finally:
            self._async_schedule(
                _CHECK_INTERVAL.total_seconds()
                + random.uniform(0, _SPREAD.total_seconds()),  # noqa: S311
            )


class BlueprintUpdateEntity(  # pylint: disable=too-many-instance-attributes
    SpookEntity,
    UpdateEntity,
):
    """Spook update entity for a single imported blueprint."""

    _attr_should_poll = False
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.RELEASE_NOTES
        | UpdateEntityFeature.BACKUP
    )

    def __init__(
        self,
        blueprint_domain: str,
        blueprint_path: str,
        said: _OnDisk,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            description=BlueprintSpookUpdateEntityDescription(
                key=f"{blueprint_domain}_{blueprint_path}",
                name=said.name,
            ),
        )
        self.blueprint_domain = blueprint_domain
        self.blueprint_path = blueprint_path

        self._attr_unique_id = _unique_id(blueprint_domain, blueprint_path)

        # Deliberately no device. These used to hang off one called
        # "Blueprints", and the updates page shows the device a row belongs to,
        # so twenty blueprints read "Blueprints" twenty times over with no way
        # to tell which was which. A device each would have fixed the reading
        # and filled the device list with twenty entries that are not devices.
        # A blueprint is a file, not a thing with firmware.

        self._said = said
        self._fetched: blueprint.Blueprint | None = None
        self._set_aside: str | None = None

        # A round of checks and somebody pressing install can land on the same
        # blueprint at the same moment, and both of them fetch before they
        # write. Whichever finished last used to win, which could leave this
        # saying an update is waiting for a version that had just been
        # installed.
        self._one_at_a_time = asyncio.Lock()

        self._attr_name = said.name
        self._attr_title = said.name
        self._attr_installed_version = said.fingerprint
        self._attr_latest_version = said.fingerprint

        # Deliberately no `release_url`. Home Assistant would put it in the
        # state attributes, which every signed-in person can read, and it lets
        # a blueprint be imported from an address carrying a token or a
        # username and password. Every one of its own blueprint commands is
        # admin only, so the address belongs with the release notes, which are
        # admin only too, and not in the states.

    @callback
    def async_seen(self, said: _OnDisk) -> None:
        """Take in a blueprint file that has been read again.

        Somebody can re-import through Home Assistant's own button, rename the
        thing, or edit it by hand, without Spook having any part in it.
        """
        if said == self._said:
            return

        self._said = said
        self._attr_name = said.name
        self._attr_title = said.name
        self._attr_installed_version = said.fingerprint
        self.async_write_ha_state()

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return whether the source says something other than what is here.

        Different is the most that can be known. These are fingerprints of the
        content, so there is no older and newer, only the same and not the
        same.
        """
        return latest_version != installed_version

    async def async_check(self) -> None:
        """See whether the source still says what this blueprint says."""
        async with self._one_at_a_time:
            await self._async_check()

    async def _async_check(self) -> None:
        """Fetch and compare, with the blueprint to ourselves."""
        try:
            fetched = await self._async_fetch()
        except HomeAssistantError as err:
            # Leave the last answer standing. A source that is down for an
            # afternoon should not take the update it was offering with it.
            # The reason is kept so the dialog can say why nothing happens
            # here, rather than looking simply idle.
            self._set_aside = str(err)
            LOGGER.debug(
                "Spook could not check blueprint %s: %s",
                self.blueprint_path,
                err,
            )
            return

        self._set_aside = None
        self._fetched = fetched
        self._attr_latest_version = _fingerprint(fetched)
        self.async_write_ha_state()

    async def async_install(
        self,
        version: str | None,  # noqa: ARG002
        backup: bool,  # noqa: FBT001
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Fetch the blueprint again and write it over the one that is here."""
        async with self._one_at_a_time:
            await self._async_install(backup=backup)

    async def _async_install(self, *, backup: bool = False) -> None:
        """Write the source over what is here, with the blueprint to ourselves."""
        fetched = await self._async_fetch()

        # The blueprint saying for itself that it needs a newer Home Assistant.
        # Writing it anyway would break every consumer on a version that is
        # never going to work.
        if errors := fetched.validate():
            msg = (
                f"{self._said.name} cannot run here: {'; '.join(errors)}. "
                f"Nothing has been written."
            )
            raise HomeAssistantError(msg)

        if short := await self._async_consumers_left_short(fetched):
            msg = (
                f"Updating {self._said.name} would stop {_listed(short)} from "
                f"loading. Nothing has been written. Put that right first, or "
                f"import {self._said.source_url} yourself from the blueprint "
                f"page if you would rather sort them out afterwards."
            )
            raise HomeAssistantError(msg)

        domain_blueprints: dict[str, blueprint.DomainBlueprints] = self.hass.data.get(
            blueprint.DOMAIN,
            {},
        )
        if (domain_blueprint := domain_blueprints.get(self.blueprint_domain)) is None:
            msg = f"{self.blueprint_domain} blueprints are not loaded right now"
            raise HomeAssistantError(msg)

        if backup:
            file = self._file()
            if file is None:  # pragma: no cover - the domain is right here
                msg = f"Could not work out where {self.blueprint_path} lives"
                raise HomeAssistantError(msg)

            try:
                await self.hass.async_add_executor_job(_keep_a_copy, file)
            except OSError as err:
                # Asked for a copy and did not get one. Writing anyway would
                # take the version that works with nothing to fall back on,
                # which is the opposite of what was asked for.
                msg = (
                    f"Could not put a copy of {self.blueprint_path} aside: "
                    f"{err}. Nothing has been written."
                )
                raise HomeAssistantError(msg) from err

        try:
            await domain_blueprint.async_add_blueprint(
                fetched,
                self.blueprint_path,
                allow_override=True,
            )
        except OSError as err:
            msg = f"Could not write {self.blueprint_path}"
            raise HomeAssistantError(msg) from err

        # A fetch that worked, so whatever the last one could not do is no
        # longer the news. Left standing, the dialog would go on saying the
        # source was unreachable until tomorrow's round.
        self._set_aside = None
        self._fetched = fetched
        self._attr_installed_version = _fingerprint(fetched)
        self._attr_latest_version = self._attr_installed_version
        self.async_write_ha_state()

    @callback
    def _file(self) -> Path | None:
        """Return the blueprint's own file, if its domain is loaded."""
        domain_blueprints: dict[str, blueprint.DomainBlueprints] = self.hass.data.get(
            blueprint.DOMAIN,
            {},
        )
        if (domain_blueprint := domain_blueprints.get(self.blueprint_domain)) is None:
            return None

        return domain_blueprint.blueprint_folder / self.blueprint_path

    async def _async_differences(self) -> str:
        """Return what the dialog says about the difference it found.

        A fingerprint on its own is an assertion: something changed, take our
        word for it. What somebody actually needs is whether this touches the
        settings they filled in, whether it changes what the thing does, or
        whether an author tidied up their wording, in which case they can stop
        reading.
        """
        if (changes := await self._async_what_differs()) is None:
            return _CANNOT_SAY_WHAT_DIFFERS

        if not changes:
            # The fetch says otherwise, and the two are measured the same way,
            # so this is not something to paper over with a cheerful sentence.
            return (
                "<ha-alert alert-type='warning'>"
                "Spook found no difference between this and the copy you have, "
                "having just been told there is one. Please report that."
                "</ha-alert>"
            )

        lines = _in_words(changes)

        if self._fetched.validate():
            # The refusal further down names the version and says Spook will
            # not write this. Saying it here as well reads as two problems.
            lines = [line for line in lines if not line.startswith(_ASKS_FOR)]

        if not lines:
            return ""

        return "\n".join([_WHAT_DIFFERS, *(f"- {line}" for line in lines)])

    async def _async_what_differs(self) -> _Changes | None:
        """Return where the fetched blueprint and the one here disagree.

        `None` when that cannot be worked out, which is worth saying out loud
        rather than quietly leaving the answer out of a dialog that is already
        asking somebody to take an update on trust.

        Read off the file rather than taken from the copy Home Assistant has
        loaded. That one has been through the domain's own schema, which
        rewrites the older spellings, and every blueprint written before those
        names changed would come out looking different from itself.
        """
        if self._fetched is None or (file := self._file()) is None:
            return None

        if (here := await self.hass.async_add_executor_job(_read_one, file)) is None:
            return None

        return _changes(here, self._fetched)

    async def async_release_notes(self) -> str | None:
        """Return what can honestly be said before somebody presses install.

        Which is not much, and that is the whole of it. A blueprint has no
        changelog and no version, so there is nothing to show you that says
        what changed. What is left is where it came from, so you can go and
        read it, and a plain warning that an author improving their blueprint
        and it still suiting what you built on it are two different things.
        """
        came_from = f"Imported from [{self._said.source_url}]({self._said.source_url})."

        nothing_on_offer = self.state != STATE_ON or self._fetched is None

        # Whatever went wrong last time round goes first either way. Left out
        # of the branch below, it would sit behind news from an older look
        # while the source itself had stopped answering.
        aside: list[str] = []
        if self._set_aside is not None:
            aside.append(
                "<ha-alert alert-type='info'>"
                + self._set_aside
                + (
                    ""
                    if nothing_on_offer
                    else " What follows is from the last look that worked."
                )
                + "</ha-alert>",
            )

        built_on_it = self._async_built_on_it()

        if nothing_on_offer:
            return "\n\n".join([*aside, came_from, built_on_it])

        notes = [
            *aside,
            _NO_PROMISES,
            came_from,
            await self._async_differences(),
            built_on_it,
        ]

        if errors := self._fetched.validate():
            notes.append(_WOULD_NOT_RUN)
            notes.extend(f"- {error}" for error in errors)

        if short := await self._async_consumers_left_short(self._fetched):
            notes.append(_WOULD_BE_REFUSED)
            notes.extend(
                f"- `{entity_id}` {reason}"
                for entity_id, reason in sorted(short.items())
            )

        return "\n\n".join(line for line in notes if line)

    async def _async_fetch(self) -> blueprint.Blueprint:
        """Fetch whatever the source URL points at now."""
        source_url = self._said.source_url

        try:
            async with asyncio.timeout(_FETCH_TIMEOUT):
                imported = await fetch_blueprint_from_url(self.hass, source_url)
        except (TimeoutError, aiohttp.ClientError) as err:
            msg = f"Could not reach {source_url}."
            raise HomeAssistantError(msg) from err
        except vol.Invalid as err:
            msg = f"{source_url} no longer holds a valid blueprint."
            raise HomeAssistantError(msg) from err
        except AssertionError as err:
            # Home Assistant's own fetchers assert that the YAML they parsed
            # is a mapping. A source answering with a list, or a bare string,
            # arrives as an AssertionError, which is nothing this would catch
            # by type and would take the whole round down with it.
            msg = f"{source_url} did not answer with a blueprint."
            raise HomeAssistantError(msg) from err

        fetched = imported.blueprint

        # A community topic can hold more than one blueprint, and the importer
        # takes the first it comes across. Every blueprint in a topic was given
        # the same source URL on the way in, so following one can land on
        # another. The domain and the name together are the most that can be
        # asked of a format that carries no identity of its own: an author
        # renaming their blueprint costs an update, writing somebody else's
        # blueprint into this file costs a lot more.
        if fetched.domain != self.blueprint_domain or fetched.name != self._said.name:
            msg = (
                f"{source_url} leads to '{fetched.name}', a {fetched.domain} "
                f"blueprint, and not to '{self._said.name}'. Spook will not "
                f"put one over the other."
            )
            raise HomeAssistantError(msg)

        return fetched

    @callback
    def _async_built_on_it(self) -> str:
        """Return what the dialog says about what is built on this blueprint.

        An update writes over a file that other things are running on, and
        which ones is not written down anywhere somebody can see. So they are
        named, with a link to each, because "what is this going to touch" is
        the first thing anybody asks and the answer used to be a shrug.
        """
        uses = _USES_BLUEPRINTS[self.blueprint_domain]

        if not (built := self._async_who_built_on_it()):
            return f"No {uses.many} are using this blueprint."

        if len(built) == 1:
            opening = f"**The following {uses.one} is using this blueprint:**"
        else:
            opening = (
                f"**The following {len(built)} {uses.many} are using this blueprint:**"
            )

        return "\n".join(
            [opening, "", *(f"- [{name}]({where})" for name, where in built)],
        )

    @callback
    def _async_who_built_on_it(self) -> list[tuple[str, str]]:
        """Return what runs on this blueprint, and where to go and edit it."""
        component = self.hass.data.get(DATA_INSTANCES, {}).get(self.blueprint_domain)
        if component is None:
            return []

        uses = _USES_BLUEPRINTS[self.blueprint_domain]
        built: list[tuple[str, str]] = []

        for entity_id in uses.users(self.hass, self.blueprint_path):
            if (entity := component.get_entity(entity_id)) is None:
                continue

            # Written in YAML without an `id:`, so there is no editor to open.
            # The overview page is the nearest thing to where it lives.
            where = (
                uses.dashboard_url
                if entity.unique_id is None
                else uses.edit_url.format(unique_id=entity.unique_id)
            )

            built.append((entity.name or entity_id, where))

        return sorted(built)

    async def _async_consumers_left_short(
        self,
        fetched: blueprint.Blueprint,
    ) -> dict[str, str]:
        """Return which users of this blueprint the new version would strand.

        Two ways it can. An input without a default has to be supplied by
        whoever uses the blueprint, so a new one that nobody sets leaves them
        with nothing to put there. And a blueprint can be perfectly good as a
        blueprint while what comes out of it is not something Home Assistant
        will run: the blueprint schema has nothing whatever to say about
        triggers, actions or a script's sequence.

        Either way they stop loading the moment this is written, and the
        version they did work with has been written over by then.

        Both questions are put to Home Assistant rather than answered again
        here, so the two cannot drift apart.
        """
        component = self.hass.data.get(DATA_INSTANCES, {}).get(self.blueprint_domain)
        if component is None:
            return {}

        uses = _USES_BLUEPRINTS[self.blueprint_domain]
        short: dict[str, str] = {}

        for entity_id in uses.users(self.hass, self.blueprint_path):
            if (entity := component.get_entity(entity_id)) is None:
                continue

            # Not `raw_config`, which is the automation after the blueprint has
            # been substituted into it and no longer says which inputs went in.
            # Reached for by name rather than as an attribute so that a rename
            # upstream reads as "cannot tell", which blocks the install rather
            # than going ahead on a guess.
            supplied = getattr(entity, "_blueprint_inputs", None)
            if supplied is None:
                short[entity_id] = "cannot be checked"
                continue

            candidate = blueprint.BlueprintInputs(fetched, supplied)

            if missing := set(fetched.inputs) - set(candidate.inputs_with_default):
                short[entity_id] = f"never sets {', '.join(sorted(missing))}"
                continue

            # Substituting cannot fail here: a blueprint whose body reaches for
            # an input it never declares is turned away when it is built, so by
            # now every one of them has a value.
            try:
                await uses.validate(
                    self.hass,
                    entity_id.partition(".")[2],
                    candidate.async_substitute(),
                )
            except (vol.Invalid, HomeAssistantError) as err:
                short[entity_id] = f"would not load: {err}"

        return short


def _listed(short: dict[str, str]) -> str:
    """Return the stranded consumers as something to put in a sentence."""
    return ", ".join(
        f"{entity_id} ({reason})" for entity_id, reason in sorted(short.items())
    )
