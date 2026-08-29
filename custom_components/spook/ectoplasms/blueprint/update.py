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
from homeassistant.components.blueprint.const import (
    CONF_INPUT,
    CONF_SOURCE_URL,
    CONF_USE_BLUEPRINT,
)
from homeassistant.components.blueprint.importer import fetch_blueprint_from_url
from homeassistant.components.script import scripts_with_blueprint
from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import CONF_DEFAULT, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import yaml as yaml_util

from ...const import DOMAIN, LOGGER
from ...entity import SpookEntity, SpookEntityDescription
from ...listeners import async_listen_once_tracked

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import Event, HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Only the domains whose blueprint users can be listed. Without that list
# there is no telling whether an update would leave an automation short of an
# input, and an install button that cannot promise that is worse than no
# button at all. Template blueprints are the ones missing out for now.
_CONSUMERS: dict[str, Callable[[HomeAssistant, str], list[str]]] = {
    "automation": automations_with_blueprint,
    "script": scripts_with_blueprint,
}

# The folder Home Assistant fills with its own example blueprints. All three
# of them carry a source URL pointing at core's dev branch, so following them
# would put an update on every installation there is, for something nobody
# imported, out of a branch that is not the one they are running.
_HOME_ASSISTANTS_OWN = f"homeassistant{os.sep}"

_CHECK_INTERVAL = timedelta(hours=24)

# Every one of these is a request to somebody else's server, and the community
# forum and GitHub between them host nearly all of it. Restarts cluster after
# a release, so the first round waits a random while rather than joining the
# stampede.
_FIRST_CHECK_WINDOW = (timedelta(minutes=5), timedelta(minutes=30))

_FETCH_TIMEOUT = 30


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an update entity for every blueprint that came from a URL."""
    await _BlueprintUpdates(hass, async_add_entities).async_start(entry)


def _fingerprint(raw: str) -> str | None:
    """Return a short hash of what a blueprint says, or None if unreadable.

    Blueprints carry no version and cannot be given one: the schema for the
    `blueprint:` block turns away keys it does not know, so an author has
    nowhere to put one. That leaves the content itself as the version.

    Both sides go through the same parse and re-dump, and deliberately not
    through the domain's own schema. That one rewrites the older spellings,
    `trigger` into `triggers` and the rest of it, and only the copy Home
    Assistant has loaded ever goes through it. Measuring that against a
    freshly fetched one would call every blueprint written before those names
    changed out of date, for ever.
    """
    try:
        parsed = yaml_util.parse_yaml(raw)
        normalized = blueprint.Blueprint(parsed, schema=BLUEPRINT_SCHEMA).yaml()
    except HomeAssistantError:
        return None

    return hashlib.sha256(normalized.encode()).hexdigest()[:8]


def _fingerprint_files(files: list[Path]) -> list[str | None]:
    """Return the fingerprint of each blueprint file, in the order given."""
    fingerprints: list[str | None] = []
    for file in files:
        try:
            raw = file.read_text(encoding="utf-8")
        except OSError:
            fingerprints.append(None)
            continue

        fingerprints.append(_fingerprint(raw))

    return fingerprints


@dataclass(frozen=True, kw_only=True)
class BlueprintSpookUpdateEntityDescription(
    SpookEntityDescription,
    UpdateEntityDescription,
):
    """Class describing Spook blueprint update entities."""


@dataclass(frozen=True, kw_only=True)
class _OnDisk:
    """A blueprint that is here, and where it came from."""

    item: blueprint.Blueprint
    file: Path


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

    async def async_start(self, entry: ConfigEntry) -> None:
        """Take stock now or once Home Assistant is up, then keep checking."""

        @callback
        def _stop() -> None:
            self._stopped = True

        entry.async_on_unload(_stop)

        if self.hass.state is CoreState.running:
            await self._async_take_stock()
        else:
            entry.async_on_unload(
                async_listen_once_tracked(
                    self.hass,
                    EVENT_HOMEASSISTANT_STARTED,
                    self._async_started,
                ),
            )

        entry.async_on_unload(
            async_call_later(
                self.hass,
                random.uniform(  # noqa: S311
                    _FIRST_CHECK_WINDOW[0].total_seconds(),
                    _FIRST_CHECK_WINDOW[1].total_seconds(),
                ),
                self._async_check_all,
            ),
        )
        entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._async_check_all,
                _CHECK_INTERVAL,
            ),
        )

    async def _async_started(self, _event: Event[Any]) -> None:
        """Take stock once the blueprint domains have registered themselves."""
        await self._async_take_stock()

    async def _async_take_stock(self) -> None:
        """Match the entities to the blueprints that are on disk."""
        found = await self._async_look()

        fingerprints = await self.hass.async_add_executor_job(
            _fingerprint_files,
            [on_disk.file for on_disk in found.values()],
        )

        await self._async_forget(set(self._entities) - set(found))

        added: list[BlueprintUpdateEntity] = []
        for (key, on_disk), fingerprint in zip(
            found.items(),
            fingerprints,
            strict=True,
        ):
            if fingerprint is None:
                # Gone or unreadable between the listing and the reading.
                # Nothing to compare against, so nothing to say.
                continue

            if (entity := self._entities.get(key)) is not None:
                entity.async_seen(on_disk.item, fingerprint)
                continue

            entity = BlueprintUpdateEntity(*key, on_disk.item, fingerprint)
            self._entities[key] = entity
            added.append(entity)

        if added:
            self._async_add_entities(added)

    async def _async_look(self) -> dict[tuple[str, str], _OnDisk]:
        """Return every blueprint that came from a URL."""
        found: dict[tuple[str, str], _OnDisk] = {}
        domain_blueprints: dict[str, blueprint.DomainBlueprints] = self.hass.data.get(
            blueprint.DOMAIN,
            {},
        )

        for domain, domain_blueprint in sorted(domain_blueprints.items()):
            if domain not in _CONSUMERS:
                continue

            for path, item in (await domain_blueprint.async_get_blueprints()).items():
                # Failed to load, or written by hand rather than imported.
                # Without a source there is nothing to check against, which
                # is also how somebody opts out: take the URL back out.
                if not isinstance(item, blueprint.Blueprint):
                    continue
                if not item.metadata.get(CONF_SOURCE_URL):
                    continue
                if path.startswith(_HOME_ASSISTANTS_OWN):
                    continue

                found[(domain, path)] = _OnDisk(
                    item=item,
                    file=domain_blueprint.blueprint_folder / path,
                )

        return found

    async def _async_forget(self, keys: set[tuple[str, str]]) -> None:
        """Drop the entities of blueprints that are no longer there."""
        if not keys:
            return

        registry = er.async_get(self.hass)
        for key in keys:
            entity = self._entities.pop(key)
            await entity.async_remove(force_remove=True)

            # The blueprint is gone for good, so the registration goes with
            # it rather than lingering as something restorable.
            if registry.async_get(entity.entity_id):
                registry.async_remove(entity.entity_id)

    async def _async_check_all(self, _now: datetime | None = None) -> None:
        """Ask every source whether it has moved on since."""
        if self._stopped:
            return

        await self._async_take_stock()

        # One at a time on purpose. These nearly all go to two hosts, and
        # nothing here is in a hurry.
        for entity in list(self._entities.values()):
            if self._stopped:
                return

            await entity.async_check()


class BlueprintUpdateEntity(  # pylint: disable=too-many-instance-attributes
    SpookEntity,
    UpdateEntity,
):
    """Spook update entity for a single imported blueprint."""

    _attr_should_poll = False
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(
        self,
        blueprint_domain: str,
        blueprint_path: str,
        item: blueprint.Blueprint,
        fingerprint: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            description=BlueprintSpookUpdateEntityDescription(
                key=f"{blueprint_domain}_{blueprint_path}",
                name=item.name,
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

        self._source_url: str = item.metadata[CONF_SOURCE_URL]
        self._attr_title = item.name
        self._attr_release_url = self._source_url
        self._attr_installed_version = fingerprint
        self._attr_latest_version = fingerprint

    @callback
    def async_seen(self, item: blueprint.Blueprint, fingerprint: str) -> None:
        """Take in a blueprint that has been read from disk again.

        Somebody can re-import through Home Assistant's own button, or rename
        the thing, without Spook having any part in it.
        """
        self._source_url = item.metadata[CONF_SOURCE_URL]
        self._attr_title = item.name
        self._attr_release_url = self._source_url

        if fingerprint == self._attr_installed_version:
            return

        self._attr_installed_version = fingerprint
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
        try:
            fetched = await self._async_fetch()
        except HomeAssistantError as err:
            # Leave the last answer standing. A source that is down for an
            # afternoon should not take the update it was offering with it.
            LOGGER.debug(
                "Spook could not check blueprint %s: %s",
                self.blueprint_path,
                err,
            )
            return

        if (fingerprint := _fingerprint(fetched.yaml())) is None:
            return

        self._attr_latest_version = fingerprint
        self.async_write_ha_state()

    async def async_install(
        self,
        version: str | None,  # noqa: ARG002
        backup: bool,  # noqa: ARG002, FBT001
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Fetch the blueprint again and write it over the one that is here."""
        fetched = await self._async_fetch()

        if short := self._async_consumers_left_short(fetched):
            listed = ", ".join(
                f"{entity_id} ({', '.join(sorted(inputs))})"
                for entity_id, inputs in sorted(short.items())
            )
            msg = (
                f"Updating {self._attr_title} would stop {listed} from loading, "
                f"because the new version asks for something they do not set. "
                f"Nothing has been written. Set those inputs first, or import "
                f"{self._source_url} yourself from the blueprint page if you are "
                f"happy to reconfigure them afterwards."
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

        self._attr_installed_version = _fingerprint(fetched.yaml())
        self._attr_latest_version = self._attr_installed_version
        self.async_write_ha_state()

    async def _async_fetch(self) -> blueprint.Blueprint:
        """Fetch whatever the source URL points at now."""
        try:
            async with asyncio.timeout(_FETCH_TIMEOUT):
                imported = await fetch_blueprint_from_url(self.hass, self._source_url)
        except (TimeoutError, aiohttp.ClientError) as err:
            msg = f"Could not reach {self._source_url}"
            raise HomeAssistantError(msg) from err
        except vol.Invalid as err:
            msg = f"{self._source_url} no longer holds a valid blueprint"
            raise HomeAssistantError(msg) from err

        if imported.blueprint.domain != self.blueprint_domain:
            # A community topic can hold more than one blueprint, and the
            # importer takes the first it comes across. Both of them were
            # given the same source URL on the way in, so following it can
            # land on the other one entirely.
            msg = (
                f"{self._source_url} leads to a {imported.blueprint.domain} "
                f"blueprint rather than {self.blueprint_domain}, so it is not "
                f"this one"
            )
            raise HomeAssistantError(msg)

        return imported.blueprint

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
        """
        required = {
            name
            for name, spec in fetched.inputs.items()
            if not isinstance(spec, dict) or CONF_DEFAULT not in spec
        }
        if not required:
            return {}

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

            # Not `raw_config`, which is the automation after the blueprint
            # has been substituted into it and no longer says which inputs
            # went in. Reached for by name rather than as an attribute so
            # that a rename upstream reads as "supplies nothing", which
            # blocks the install rather than going ahead on a guess.
            inputs = getattr(entity, "_blueprint_inputs", None) or {}
            used = inputs.get(CONF_USE_BLUEPRINT) or {}

            if missing := required - set(used.get(CONF_INPUT) or ()):
                short[entity_id] = missing

        return short
