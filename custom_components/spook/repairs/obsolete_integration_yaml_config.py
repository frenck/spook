"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.config import async_hass_config_yaml
from homeassistant.exceptions import HomeAssistantError

from ..const import DOMAIN, LOGGER
from . import AbstractSpookSingleShotRepairs


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
        "canary",
        "cast",
        "cloudflare",
        "coinbase",
        "daikin",
        "directv",
        "doorbird",
        "freebox",
        "glances",
        "google",
        "heos",
        "hive",
        "home_connect",
        "hue",
        "hunterdouglas_powerview",
        "icloud",
        "islamic_prayer_times",
        "isy994",
        "juicenet",
        "lametric",
        "life360",
        "lifx",
        "litejet",
        "local_ip",
        "luftdaten",
        "lyric",
        "melcloud",
        "meteo_france",
        "mikrotik",
        "mysensors",
        "neato",
        "netatmo",
        "nfandroidtv",
        "notion",
        "nuheat",
        "nzbget",
        "octoprint",
        "pi_hole",
        "plum_lightpad",
        "powerwall",
        "pvpc_hourly_pricing",
        "rachio",
        "rainbird",
        "rainmachine",
        "roku",
        "samsungtv",
        "sentry",
        "senz",
        "simplisafe",
        "skybell",
        "solaredge",
        "soma",
        "somfy_mylink",
        "spider",
        "spotify",
        "switcher_kis",
        "synology_dsm",
        "tado",
        "tankerkoenig",
        "tibber",
        "totalconnect",
        "tradfri",
        "transmission",
        "upnp",
        "vallox",
        "vera",
        "verisure",
        "vesync",
        "volvooncall",
        "webostv",
        "xbox",
    }

    async def async_inspect(self) -> None:
        """Trigger a single shot repair."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

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
                    "YAML configuration and created an issue; domain: %s",
                    domain,
                )
