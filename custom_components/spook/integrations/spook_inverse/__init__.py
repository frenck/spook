"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
    async_remove_helper_devices,
)

from .config_flow import SpookInverseConfigFlowHandler
from .const import CONF_HIDE_SOURCE, DOMAIN

MIGRATION_MINOR_VERSION = SpookInverseConfigFlowHandler.MINOR_VERSION

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


@callback
def async_get_source_entity_device_id(
    hass: HomeAssistant, entity_id: str
) -> str | None:
    """Get the entity device id."""
    registry = er.async_get(hass)

    if not (resolved_entity_id := er.async_resolve_entity_id(registry, entity_id)):
        return None
    if not (source_entity := registry.async_get(resolved_entity_id)):
        return None

    return source_entity.device_id


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    source = entry.options[CONF_ENTITY_ID]

    # Remembered for when the options change, which is the only moment the
    # previous source, and whether this inverse hid it, is still known.
    # Somebody pointing the inverse elsewhere would otherwise leave the old
    # one hidden for good.
    entry.runtime_data = (source, entry.options[CONF_HIDE_SOURCE])

    @callback
    def _follow_the_source(source_entity_id: str) -> None:
        """Keep up with the source being renamed, the way core helpers do.

        The inverse listens to its source by entity ID, and a rename gives it
        a new one: without this it keeps listening to a name nobody uses and
        switching something that is not there.
        """
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_ENTITY_ID: source_entity_id}
        )

    # A source stored as a registry ID that is gone resolves to nothing, and
    # Home Assistant raises on following that. The inverse still sets up, and
    # is unavailable, which is the truth about it.
    if er.async_resolve_entity_id(er.async_get(hass), source):
        entry.async_on_unload(
            async_handle_source_entity_changes(
                hass,
                helper_config_entry_id=entry.entry_id,
                set_source_entity_id_or_uuid=_follow_the_source,
                source_device_id=async_get_source_entity_device_id(hass, source),
                source_entity_id_or_uuid=source,
            )
        )

    await hass.config_entries.async_forward_entry_setups(
        entry,
        (entry.options["inverse_type"],),
    )
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed.

    Hiding happens in the options flow. Showing the source again happens
    here, because only here are both the old options and the new ones known,
    and showing it again is only this inverse's to do if it was the one that
    hid it.
    """
    previous_source, previously_hidden = entry.runtime_data
    if previously_hidden and (
        previous_source != entry.options[CONF_ENTITY_ID]
        or not entry.options[CONF_HIDE_SOURCE]
    ):
        async_release_source(hass, previous_source)

    await hass.config_entries.async_reload(entry.entry_id)


@callback
def async_release_source(hass: HomeAssistant, source: str) -> None:
    """Show a source again that this inverse hid and no longer hides.

    Only if Spook hid it, and only if no other inverse still wants it hidden:
    two inverses of one source share the hiding, and one of them letting go
    is not the other one letting go. After a rename the old name is in the
    registry no more, and the entry that is, with its hiding, is left alone.
    """
    registry = er.async_get(hass)
    if not (entity_id := er.async_resolve_entity_id(registry, source)):
        return
    if (entity_entry := registry.async_get(entity_id)) is None:
        return
    if entity_entry.hidden_by != er.RegistryEntryHider.INTEGRATION:
        return

    # Every inverse as it is now, this one with its new options. A removed
    # one is already gone from the list by the time it is asked about.
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.options.get(CONF_HIDE_SOURCE) and (
            er.async_resolve_entity_id(registry, other.options[CONF_ENTITY_ID])
            == entity_id
        ):
            return

    registry.async_update_entity(entity_id, hidden_by=None)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry,
        (entry.options["inverse_type"],),
    )


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry, unhide the source entity."""
    if entry.options[CONF_HIDE_SOURCE]:
        async_release_source(hass, entry.options[CONF_ENTITY_ID])


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if (
        config_entry.version == 1 and config_entry.minor_version < 2  # noqa: PLR2004
    ):
        options = {**config_entry.options}
        if (source_entity_id := options.get(CONF_ENTITY_ID)) and (
            source_device_id := async_get_source_entity_device_id(
                hass, source_entity_id
            )
        ):
            # Remove the spook_inverse config entry from the source device
            async_remove_helper_devices(
                hass,
                helper_config_entry_id=config_entry.entry_id,
                source_device_id=source_device_id,
            )
        hass.config_entries.async_update_entry(
            config_entry, options=options, minor_version=MIGRATION_MINOR_VERSION
        )

    return True
