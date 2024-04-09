"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.components.homeassistant import (
    DOMAIN,
    SERVICE_HOMEASSISTANT_RESTART,
    SERVICE_RELOAD_ALL,
)
from homeassistant.const import EntityCategory

from ...entity import SpookEntityDescription
from .entity import HomeAssistantSpookEntity

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class HomeAssistantSpookButtonEntityDescription(
    SpookEntityDescription,
    ButtonEntityDescription,
):
    """Class describing Spook Home Assistant button entities."""

    press_fn: Callable[[HomeAssistant], Awaitable[Any]]


BUTTONS: tuple[HomeAssistantSpookButtonEntityDescription, ...] = (
    HomeAssistantSpookButtonEntityDescription(
        key="restart",
        translation_key="homeassistant_restart",
        entity_id="button.homeassistant_restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda hass: hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEASSISTANT_RESTART,
            blocking=True,
        ),
    ),
    HomeAssistantSpookButtonEntityDescription(
        key="reload",
        translation_key="homeassistant_reload",
        entity_id="button.homeassistant_reload",
        icon="mdi:auto-fix",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda hass: hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD_ALL,
            blocking=True,
        ),
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    _entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook sensor."""
    async_add_entities(
        HomeAssistantSpookButtonEntity(description) for description in BUTTONS
    )


class HomeAssistantSpookButtonEntity(HomeAssistantSpookEntity, ButtonEntity):
    """Spook button providig Home Asistant actions."""

    entity_description: HomeAssistantSpookButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.hass)
