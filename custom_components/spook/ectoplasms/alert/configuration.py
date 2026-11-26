"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.components.alert.const import CONF_NOTIFIERS, DOMAIN
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.util.hass_dict import HassKey

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


# The alerts as read the first time, for the rest of the run. Home Assistant
# has no way to reload alerts: what it set up at the start is what runs
# until it restarts, so reading the file again only finds the same alerts,
# or edits that are not running yet.
_ALERT_CONFIGURATIONS: HassKey[tuple[AlertConfiguration, ...]] = HassKey(
    "spook_alert_configurations"
)


async def async_get_alert_configurations(
    hass: HomeAssistant,
) -> tuple[AlertConfiguration, ...]:
    """Return the configured alerts, read back from the YAML configuration.

    Alerts are YAML-only and their entities keep almost nothing in public:
    the watched entity ID and the notifiers only live in private attributes.
    Reading the configuration back is the way to see what an alert actually
    points at without reaching into those.

    Development of the alert integration is frozen upstream, so this shape is
    not going to move under us.

    Raises when the configuration cannot be read or will not validate. That
    is deliberate: an empty answer means "no alerts", and a configuration Spook
    could not read means nothing of the sort. Letting it raise aborts the
    inspection before its issue cleanup runs, so alerts that were already
    reported stay reported until Spook can actually look again.

    Read once per run, see `_ALERT_CONFIGURATIONS`. Reading it means reading
    and validating all of the configuration, packages included, which on a
    large one took seconds, on every inspection of both alert repairs. A
    read that fails is not remembered, so the next inspection tries again.
    """
    if DOMAIN not in hass.config.components:
        return ()  # Alert is not set up, so there is nothing to read.

    if (known := hass.data.get(_ALERT_CONFIGURATIONS)) is not None:
        return known

    # Reads configuration.yaml from disk, in the executor.
    config = await async_integration_yaml_config(hass, DOMAIN, raise_on_failure=True)
    if not (alerts := config.get(DOMAIN)):
        LOGGER.debug("Spook found no alert configuration to inspect")
        alerts = {}

    known = tuple(
        AlertConfiguration(
            object_id=object_id,
            name=settings.get(CONF_NAME, object_id),
            watched_entity_id=settings.get(CONF_ENTITY_ID),
            notifiers=settings.get(CONF_NOTIFIERS) or [],
        )
        for object_id, settings in alerts.items()
        if settings
    )
    hass.data[_ALERT_CONFIGURATIONS] = known
    return known
