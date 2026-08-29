"""Spook - Your homie. Updates for blueprints that came from somewhere."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import os
import random
from typing import TYPE_CHECKING, Any

import aiohttp
import voluptuous as vol

from homeassistant.components import blueprint
from homeassistant.components.automation import automations_with_blueprint
from homeassistant.components.blueprint import BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.const import CONF_SOURCE_URL
from homeassistant.components.blueprint.importer import fetch_blueprint_from_url
from homeassistant.components.script import scripts_with_blueprint
from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_ON
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.event import async_call_later
from homeassistant.util import yaml as yaml_util

from ...const import DOMAIN, LOGGER
from ...entity import SpookEntity, SpookEntityDescription
from ...listeners import async_listen_once_tracked

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Only the domains whose blueprint users can be listed. Without that list there
# is no telling whether an update would leave an automation short of an input,
# and an install button that cannot promise that is worse than no button at
# all. Template blueprints are the ones missing out for now.
_CONSUMERS: dict[str, Callable[[HomeAssistant, str], list[str]]] = {
    "automation": automations_with_blueprint,
    "script": scripts_with_blueprint,
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
    "Blueprints carry no changelog, so there is nothing here that says what "
    "changed. An update is whatever the author decided to do, and nothing "
    "promises it still fits the automations you built on it: inputs get "
    "renamed, behaviour gets rethought. Read the source before you install it."
    "</ha-alert>"
)

_WOULD_NOT_RUN = (
    "<ha-alert alert-type='error'>"
    "This version says it needs a newer Home Assistant than the one you are "
    "running, so Spook will not install it."
    "</ha-alert>"
)

_WOULD_BE_REFUSED = (
    "<ha-alert alert-type='error'>"
    "This one asks for inputs that nothing has set, so Spook will not install "
    "it. Set them first, or import it yourself from the blueprint page if you "
    "are happy to go round the automations below afterwards."
    "</ha-alert>"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an update entity for every blueprint that came from a URL."""
    await _BlueprintUpdates(hass, async_add_entities).async_start(entry)


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


def _fingerprint(item: blueprint.Blueprint) -> str:
    """Return a short hash of what a blueprint says.

    Blueprints carry no version and cannot be given one: the schema for the
    `blueprint:` block turns away keys it does not know, so an author has
    nowhere to put one. That leaves the content itself as the version.
    """
    return hashlib.sha256(item.yaml().encode()).hexdigest()[:8]


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
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize the manager."""
        self.hass = hass
        self._async_add_entities = async_add_entities
        self._entities: dict[tuple[str, str], BlueprintUpdateEntity] = {}
        self._stopped = False
        self._cancel: CALLBACK_TYPE | None = None

    async def async_start(self, entry: ConfigEntry) -> None:
        """Begin now, or once Home Assistant is up.

        Nothing is scheduled before then either. Starting up can take longer
        than the wait before the first round, and a round that lands in the
        middle of it looks at blueprint domains that have not finished
        arriving, and goes out to the internet while the house is still
        getting dressed.
        """
        entry.async_on_unload(self._stop)

        if self.hass.state is CoreState.running:
            await self._async_begin()
            return

        entry.async_on_unload(
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
        files = await self._async_look()
        on_disk = await self.hass.async_add_executor_job(
            _read_files,
            list(files.values()),
        )

        followed: dict[tuple[str, str], _OnDisk] = {}
        unreadable: set[tuple[str, str]] = set()
        for key, said in zip(files, on_disk, strict=True):
            if said is None:
                unreadable.add(key)
            elif said.source_url is not None:
                followed[key] = said

        # A file that could not be read this time round says nothing either
        # way, so whatever is already here stays. A file that was read and no
        # longer names a source is somebody asking to be left alone, and that
        # one goes.
        await self._async_forget(set(self._entities) - set(followed) - unreadable)

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

    async def _async_look(self) -> dict[tuple[str, str], Path]:
        """Return the file behind every blueprint Home Assistant can load."""
        files: dict[tuple[str, str], Path] = {}
        domain_blueprints: dict[str, blueprint.DomainBlueprints] = self.hass.data.get(
            blueprint.DOMAIN,
            {},
        )

        for domain, domain_blueprint in sorted(domain_blueprints.items()):
            if domain not in _CONSUMERS:
                continue

            for path, item in (await domain_blueprint.async_get_blueprints()).items():
                # Failed to load, or Home Assistant's own examples.
                if not isinstance(item, blueprint.Blueprint):
                    continue
                if path.startswith(_HOME_ASSISTANTS_OWN):
                    continue

                files[(domain, path)] = domain_blueprint.blueprint_folder / path

        return files

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
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
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

        self._attr_unique_id = f"blueprint_{blueprint_domain}_{blueprint_path}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, blueprint.DOMAIN)},
            manufacturer="Home Assistant",
            name="Blueprints",
        )

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
        self._attr_release_url = said.source_url
        self._attr_installed_version = said.fingerprint
        self._attr_latest_version = said.fingerprint

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
        self._attr_release_url = said.source_url
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
        backup: bool,  # noqa: ARG002, FBT001
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Fetch the blueprint again and write it over the one that is here."""
        async with self._one_at_a_time:
            await self._async_install()

    async def _async_install(self) -> None:
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

        if short := self._async_consumers_left_short(fetched):
            msg = (
                f"Updating {self._said.name} would stop {_listed(short)} from "
                f"loading, because the new version asks for something they do "
                f"not set. Nothing has been written. Set those inputs first, "
                f"or import {self._said.source_url} yourself from the "
                f"blueprint page if you are happy to reconfigure them "
                f"afterwards."
            )
            raise HomeAssistantError(msg)

        domain_blueprints: dict[str, blueprint.DomainBlueprints] = self.hass.data.get(
            blueprint.DOMAIN,
            {},
        )
        if (domain_blueprint := domain_blueprints.get(self.blueprint_domain)) is None:
            msg = f"{self.blueprint_domain} blueprints are not loaded right now"
            raise HomeAssistantError(msg)

        try:
            await domain_blueprint.async_add_blueprint(
                fetched,
                self.blueprint_path,
                allow_override=True,
            )
        except OSError as err:
            msg = f"Could not write {self.blueprint_path}"
            raise HomeAssistantError(msg) from err

        self._fetched = fetched
        self._attr_installed_version = _fingerprint(fetched)
        self._attr_latest_version = self._attr_installed_version
        self.async_write_ha_state()

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

        if nothing_on_offer:
            return "\n\n".join([*aside, came_from])

        notes = [*aside, _NO_PROMISES, came_from]

        if errors := self._fetched.validate():
            notes.append(_WOULD_NOT_RUN)
            notes.extend(f"- {error}" for error in errors)

        if short := self._async_consumers_left_short(self._fetched):
            notes.append(_WOULD_BE_REFUSED)
            notes.extend(
                f"- `{entity_id}` never sets "
                + ", ".join(f"`{name}`" for name in sorted(inputs))
                if inputs
                else f"- `{entity_id}` cannot be checked"
                for entity_id, inputs in sorted(short.items())
            )

        return "\n\n".join(notes)

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
    def _async_consumers_left_short(
        self,
        fetched: blueprint.Blueprint,
    ) -> dict[str, set[str]]:
        """Return which users of this blueprint the new version would strand.

        An input without a default has to be supplied by whoever uses the
        blueprint. If a new version asks for one that an automation never set,
        that automation stops loading the moment this is written, and there is
        no going back to the version it did work with.

        Put to Home Assistant's own reckoning of what an input needs rather
        than worked out again here, so the two cannot drift apart.
        """
        component = self.hass.data.get(DATA_INSTANCES, {}).get(self.blueprint_domain)
        if component is None:
            return {}

        short: dict[str, set[str]] = {}
        for entity_id in _CONSUMERS[self.blueprint_domain](
            self.hass,
            self.blueprint_path,
        ):
            if (entity := component.get_entity(entity_id)) is None:
                continue

            # Not `raw_config`, which is the automation after the blueprint has
            # been substituted into it and no longer says which inputs went in.
            # Reached for by name rather than as an attribute so that a rename
            # upstream reads as "cannot tell", which blocks the install rather
            # than going ahead on a guess.
            supplied = getattr(entity, "_blueprint_inputs", None)
            if supplied is None:
                short[entity_id] = set()
                continue

            candidate = blueprint.BlueprintInputs(fetched, supplied)

            # Enough on its own. A blueprint whose body reaches for an input
            # it never declares is turned away when it is built, so once every
            # declared input has a value there is nothing left for the
            # substitution to trip over.
            if missing := set(fetched.inputs) - set(candidate.inputs_with_default):
                short[entity_id] = missing

        return short


def _listed(short: dict[str, set[str]]) -> str:
    """Return the stranded consumers as something to put in a sentence."""
    return ", ".join(
        f"{entity_id} ({', '.join(sorted(inputs))})" if inputs else entity_id
        for entity_id, inputs in sorted(short.items())
    )
