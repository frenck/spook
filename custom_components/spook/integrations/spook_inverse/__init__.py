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
from .const import CONF_HIDE_SOURCE

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
    # previous source is still known. Somebody pointing the inverse at a
    # different entity would otherwise leave the old one hidden for good.
    entry.runtime_data = source

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
    """Update listener, called when the config entry options are changed."""
    if (previous := entry.runtime_data) != entry.options[CONF_ENTITY_ID]:
        _async_unhide_former_source(hass, entry, previous)

    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_unhide_former_source(
    hass: HomeAssistant,
    entry: ConfigEntry,
    former_source: str,
) -> None:
    """Show a source again that this inverse hid and no longer follows.

    Only if Spook hid it, and only if no other inverse still wants it hidden.
    A rename is not this: the registry entry is the same one, and its hidden
    state went along with it.
    """
    registry = er.async_get(hass)
    if not (entity_id := er.async_resolve_entity_id(registry, former_source)):
        return
    if (entity_entry := registry.async_get(entity_id)) is None:
        return
    if entity_entry.hidden_by != er.RegistryEntryHider.INTEGRATION:
        return
    if entity_id == er.async_resolve_entity_id(registry, entry.options[CONF_ENTITY_ID]):
        return

    for other in hass.config_entries.async_entries(entry.domain):
        if (
            other.entry_id != entry.entry_id
            and other.options.get(CONF_HIDE_SOURCE)
            and er.async_resolve_entity_id(registry, other.options[CONF_ENTITY_ID])
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
    registry = er.async_get(hass)
    if not entry.options[CONF_HIDE_SOURCE]:
        return
    if not (
        entity_id := er.async_resolve_entity_id(registry, entry.options[CONF_ENTITY_ID])
    ):
        return
    if (entity_entry := registry.async_get(entity_id)) is None:
        return
    if entity_entry.hidden_by != er.RegistryEntryHider.INTEGRATION:
        return

    registry.async_update_entity(entity_id, hidden_by=None)


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
