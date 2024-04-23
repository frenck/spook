"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.cloud import DOMAIN as CLOUD_DOMAIN
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory

from ...entity import SpookEntityDescription
from .entity import HomeAssistantCloudSpookEntity

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from hass_nabucasa import Cloud

    from homeassistant.components.cloud.client import CloudClient
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class HomeAssistantCloudSpookSwitchEntityDescription(
    SpookEntityDescription,
    SwitchEntityDescription,
):
    """Class describing Spook Home Assistant sensor entities."""

    is_on_fn: Callable[[Cloud[CloudClient]], bool | None]
    set_fn: Callable[[Cloud[CloudClient], bool], Awaitable[Any]]


SWITCHES: tuple[HomeAssistantCloudSpookSwitchEntityDescription, ...] = (
    HomeAssistantCloudSpookSwitchEntityDescription(
        key="alexa",
        entity_id="switch.cloud_alexa",
        name="Alexa",
        icon="mdi:account-voice",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda cloud: cloud.client.prefs.alexa_enabled,
        set_fn=lambda cloud, enabled: cloud.client.prefs.async_update(
            alexa_enabled=enabled,
        ),
    ),
    HomeAssistantCloudSpookSwitchEntityDescription(
        key="alexa_report_state",
        translation_key="cloud_alexa_report_state",
        entity_id="switch.cloud_alexa_report_state",
        icon="mdi:account-voice",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda cloud: cloud.client.prefs.alexa_report_state,
        set_fn=lambda cloud, enabled: cloud.client.prefs.async_update(
            alexa_report_state=enabled,
        ),
    ),
    HomeAssistantCloudSpookSwitchEntityDescription(
        key="google",
        entity_id="switch.cloud_google",
        name="Google Assistant",
        icon="mdi:google-assistant",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda cloud: cloud.client.prefs.google_enabled,
        set_fn=lambda cloud, enabled: cloud.client.prefs.async_update(
            google_enabled=enabled,
        ),
    ),
    HomeAssistantCloudSpookSwitchEntityDescription(
        key="google_report_state",
        translation_key="cloud_google_report_state",
        entity_id="switch.cloud_google_report_state",
        icon="mdi:google-assistant",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda cloud: cloud.client.prefs.google_report_state,
        set_fn=lambda cloud, enabled: cloud.client.prefs.async_update(
            google_report_state=enabled,
        ),
    ),
    HomeAssistantCloudSpookSwitchEntityDescription(
        key="remote",
        translation_key="cloud_remote",
        entity_id="switch.cloud_remote",
        icon="mdi:remote-desktop",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda cloud: cloud.client.prefs.remote_enabled,
        set_fn=lambda cloud, enabled: cloud.client.prefs.async_update(
            remote_enabled=enabled,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    _entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook Home Assistant Cloud switches."""
    if CLOUD_DOMAIN in hass.config.components:
        cloud: Cloud[CloudClient] = hass.data[CLOUD_DOMAIN]
        async_add_entities(
            HomeAssistantCloudSpookSwitchEntity(cloud, description)
            for description in SWITCHES
        )


class HomeAssistantCloudSpookSwitchEntity(HomeAssistantCloudSpookEntity, SwitchEntity):
    """Spook switch providig Home Asistant Cloud controls."""

    entity_description: HomeAssistantCloudSpookSwitchEntityDescription

    async def async_added_to_hass(self) -> None:
        """Register for switch updates."""

        async def _update_state(_: Any) -> None:
            """Update state."""
            self.async_schedule_update_ha_state()

        self.async_on_remove(
            self._cloud.client.prefs.async_listen_updates(_update_state),
        )

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        if self.entity_description.icon and self.is_on is False:
            return self.entity_description.icon
        return super().icon

    @property
    def is_on(self) -> bool | None:
        """Return state of the switch."""
        return self.entity_description.is_on_fn(self._cloud)

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.set_fn(self._cloud, True)  # noqa: FBT003

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.set_fn(self._cloud, False)  # noqa: FBT003
