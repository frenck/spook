"""Spook - Your homie. Custom integration for Home Assistant."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    RESTART_EXIT_CODE,
)
from homeassistant.core import (
    CoreState,
    callback,
)
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, LOGGER, PLATFORMS
from .repairs import SpookRepairManager
from .services import SpookServiceManager
from .util import (
    async_forward_setup_entry,
    async_setup_all_entity_ids_cache_invalidation,
    link_sub_integrations,
    unlink_sub_integrations,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import Event, HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    # Symlink all sub integrations from Spook to the parent integrations folder
    # if one is missing, we have to restart Home Assistant.
    # This is a workaround for the fact that Home Assistant doesn't support
    # sub integrations.
    if await hass.async_add_executor_job(link_sub_integrations, hass):
        LOGGER.debug("Newly symlinked sub integrations, restarting Home Assistant")

        @callback
        def _restart(_: Event | None = None) -> None:
            """Restart Home Assistant."""
            hass.data["homeassistant_stop"] = asyncio.create_task(
                hass.async_stop(RESTART_EXIT_CODE),
            )

        # User asked to restart Home Assistant in the config flow.
        if hass.data.get(DOMAIN) == "Boo!":
            _restart()
            return False

        # Should be OK to restart. Better to do it before anything else started.
        if hass.state == CoreState.starting:
            _restart()
            return False

        # If all other fails, but we are not running yet... wait for it.
        if hass.state == CoreState.not_running:
            # Listen to both... just in case.
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _restart)
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _restart)
            return False

        LOGGER.info(
            "Home Assistant needs to be restarted in for Spook to complete setting up",
        )
        ir.async_create_issue(
            hass=hass,
            domain=DOMAIN,
            issue_id="restart_required",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="restart_required",
        )

    # Forward async_setup_entry to ectoplasms
    await async_forward_setup_entry(hass, entry)

    # Set up services
    services = SpookServiceManager(hass)
    await services.async_setup()
    entry.async_on_unload(services.async_on_unload)

    # Who you gonna call? SpookRepairManager!
    repairs = SpookRepairManager(hass)

    _ghost_busters_unsub: Callable[[], None] | None = None

    async def _ghost_busters(_: Event) -> None:
        """Send them in, time for some ghost chasing."""
        await repairs.async_setup()
        entry.async_on_unload(repairs.async_on_unload)

    @callback
    def _unsubscribe_ghost_busters() -> None:
        """Unsubscribe the ghost busters listener."""
        if _ghost_busters_unsub:
            try:
                _ghost_busters_unsub()
            except ValueError:
                LOGGER.debug(
                    "Failed to unsubscribe _ghost_busters listener, "
                    "it might have already been removed or never registered.",
                )

    # Wait until Home Assistant is started, before doing repairs
    _ghost_busters_unsub = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED, _ghost_busters
    )
    entry.async_on_unload(_unsubscribe_ghost_busters)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up the all entity ids cache invalidation
    entry.async_on_unload(async_setup_all_entity_ids_cache_invalidation(hass))

    # Yay, we didn't got spooked!
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, _: ConfigEntry) -> None:
    """Remove a config entry."""
    await hass.async_add_executor_job(unlink_sub_integrations, hass)
