"""Spook - Your homie. What the repairs about dashboard resources share.

When to look at the list of resources, and how to get at it once they do.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_LOVELACE_UPDATED

from ...const import LOGGER
from ...dashboard_resources import async_watch_resources
from ...repairs import AbstractSpookRepair


class AbstractSpookDashboardResourcesRepair(AbstractSpookRepair, ABC):
    """A repair that reports something about the list of dashboard resources."""

    domain = DOMAIN
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
    }
    automatically_clean_up_issues = True

    async def async_activate(self) -> None:
        """Activate, and also watch the resource list itself.

        `inspect_events` covers component loads and dashboard saves. Neither
        fires when somebody adds or removes a resource, so without this the
        next look at them is a restart away.
        """
        await super().async_activate()

        if (
            unsub := async_watch_resources(self.hass, self._async_resources_changed)
        ) is not None:
            self._event_subs.add(unsub)

    async def _async_resources_changed(  # pylint: disable=unused-argument
        self,
        change_type: str,  # noqa: ARG002
        item_id: str,  # noqa: ARG002
        config: dict,  # noqa: ARG002
    ) -> None:
        """Look again, once the changes stop arriving."""
        await self.inspect_debouncer.async_call()

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        # Reached straight rather than guarded: Lovelace is a hard dependency
        # in the manifest, so Home Assistant has set it up before Spook. A
        # guard here would be worse than none, because returning early counts
        # as a clean inspection and cleanup would then delete every issue this
        # repair has, ignored ones included. If that invariant ever breaks, a
        # KeyError is what should happen: it leaves the bookkeeping intact.
        if (resources := self.hass.data[DOMAIN].resources) is None:
            return

        # Storage-mode resources are loaded the first time somebody asks for
        # them, which is normally the dashboard, and Spook inspects long
        # before that. Reading them straight would see an empty collection and
        # report nothing at all. In YAML mode this is already loaded and the
        # call costs nothing.
        await resources.async_get_info()

        await self._async_inspect_resources(resources)

    @abstractmethod
    async def _async_inspect_resources(self, resources: Any) -> None:
        """Report what is wrong in the resources, now that they are loaded.

        Handed the collection Home Assistant keeps them in, which is another
        integration's object: storage-mode or YAML, see `is_yaml_managed`.
        """
