"""Spook - Your homie. A shortcut past HACS's own update check schedule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory, Platform
from homeassistant.helpers import entity_registry as er

from ...entity import SpookEntityDescription
from .entity import HACS_DOMAIN, HACSSpookEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class HACSSpookButtonEntityDescription(
    SpookEntityDescription,
    ButtonEntityDescription,
):
    """Class describing Spook HACS button entities."""


async def async_setup_entry(
    hass: HomeAssistant,
    _entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Spook HACS check-for-updates button.

    Only put up when HACS itself is loaded. Without it there is nothing to
    ask, and a button that always errors out on press is worse than no
    button at all.
    """
    if HACS_DOMAIN not in hass.config.components:
        return

    async_add_entities(
        [
            HACSCheckForUpdatesButtonEntity(
                HACSSpookButtonEntityDescription(
                    key="check_for_updates",
                    translation_key="hacs_check_for_updates",
                    entity_id="button.hacs_check_for_updates",
                    icon="mdi:update",
                    entity_category=EntityCategory.CONFIG,
                ),
            ),
        ],
    )


class HACSCheckForUpdatesButtonEntity(HACSSpookEntity, ButtonEntity):
    """Spook button that has HACS look for updates right now.

    Pressing it asks Home Assistant to poll every one of HACS's own update
    entities straight away: the same as calling `homeassistant.update_entity`
    on all of them by hand, for whoever would rather not open Developer Tools
    to do it. HACS decides what counts as an update; this only decides when
    HACS is asked.
    """

    entity_description: HACSSpookButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        registry = er.async_get(self.hass)
        entity_ids = [
            entry.entity_id
            for entry in registry.entities.values()
            if entry.platform == HACS_DOMAIN and entry.domain == Platform.UPDATE
        ]

        # Nothing tracked yet, so nothing to ask about. Calling the service
        # with an empty list of entities is not the same as calling it with
        # none at all: that would poll every update entity Home Assistant
        # has, HACS's or not, which is not what pressing this button says.
        if not entity_ids:
            return

        await self.hass.services.async_call(
            HOMEASSISTANT_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: entity_ids},
            blocking=True,
        )
