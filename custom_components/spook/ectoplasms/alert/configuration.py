"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.components.alert.const import CONF_NOTIFIERS, DOMAIN
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.helpers.reload import async_integration_yaml_config

from ...const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@dataclass(frozen=True, slots=True)
class AlertConfiguration:
    """A single configured alert, as far as Spook needs to know it."""

    object_id: str
    name: str
    watched_entity_id: str | None
    notifiers: list[str] = field(default_factory=list)

    @property
    def entity_id(self) -> str:
        """Return the entity ID Home Assistant gives this alert."""
        return f"{DOMAIN}.{self.object_id}"


async def async_get_alert_configurations(
    hass: HomeAssistant,
) -> list[AlertConfiguration]:
    """Return the configured alerts, read back from the YAML configuration.

    Alerts are YAML-only and their entities keep almost nothing: the watched
    entity ID is handed straight to a state listener and never stored, so
    there is nothing to read it back from. Re-reading the configuration is
    the only way to see what an alert actually points at.

    Development of the alert integration is frozen upstream, so this shape is
    not going to move under us.
    """
    if DOMAIN not in hass.config.components:
        return []  # Alert is not set up, so there is nothing to read.

    # Re-reads configuration.yaml from disk, in the executor. Cheap enough for
    # a debounced inspection, and only ever reached by the few setups that use
    # alerts at all.
    config = await async_integration_yaml_config(hass, DOMAIN)
    if not config or not (alerts := config.get(DOMAIN)):
        LOGGER.debug("Spook found no alert configuration to inspect")
        return []

    return [
        AlertConfiguration(
            object_id=object_id,
            name=settings.get(CONF_NAME, object_id),
            watched_entity_id=settings.get(CONF_ENTITY_ID),
            notifiers=settings.get(CONF_NOTIFIERS) or [],
        )
        for object_id, settings in alerts.items()
        if settings
    ]
