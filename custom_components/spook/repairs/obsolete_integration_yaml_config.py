"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.config import async_hass_config_yaml
from homeassistant.exceptions import HomeAssistantError

from . import AbstractSpookSingleShotRepairs
from ..const import DOMAIN, LOGGER


class SpookRepair(AbstractSpookSingleShotRepairs):
    """Spook repairs that triggers that raises issues for obsolete YAML config."""

    domain = DOMAIN
    repair = "obsolete_integration_yaml_config"

    KNOWN_REMOVED_DOMAINS = {
        "abode",
        "airvisual",
        "ambient_station",
        "android_ip_webcam",
        "apcupsd",
        "arcam_fmj",
        "bmw_connected_drive",
        "cast",
        "cloudflare",
        "coinbase",
        "daikin",
        "directv",
        "doorbird",
        "glances",
        "google",
        "hue",
        "hunterdouglas_powerview",
        "icloud",
        "islamic_prayer_times",
        "life360",
        "local_ip",
        "luftdaten",
        "lyric",
        "mikrotik",
        "mysensors",
        "nfandroidtv",
        "notion",
        "nuheat",
        "nzbget",
        "pi_hole",
        "powerwall",
        "pvpc_hourly_pricing",
        "rachio",
        "rainmachine",
        "roku",
        "sentry",
        "senz",
        "simplisafe",
        "solaredge",
        "somfy_mylink",
        "spotify",
        "synology_dsm",
        "tado",
        "tankerkoenig",
        "tibber",
        "totalconnect",
        "tradfri",
        "transmission",
        "upnp",
        "verisure",
        "vesync",
        "webostv",
    }

    async def async_inspect(self) -> None:
        """Trigger a single shot repair."""
        LOGGER.debug(f"Spook is inspecting: {self.repair}")

        try:
            config = await async_hass_config_yaml(self.hass)
        except HomeAssistantError:
            LOGGER.exception("Failed to parse configuration.yaml")
            raise

        for domain in self.KNOWN_REMOVED_DOMAINS:
            if domain in config:
                self.async_create_issue(
                    issue_id=domain,
                    translation_placeholders={
                        "domain": domain,
                    },
                )
                LOGGER.debug(
                    "Spook found a known invalid integration domain in the "
                    f"YAML configuration and created an issue; domain: {domain}"
                )
