"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.config import async_hass_config_yaml
from homeassistant.const import Platform
from homeassistant.exceptions import HomeAssistantError

from ..const import DOMAIN, LOGGER
from . import AbstractSpookSingleShotRepairs


class SpookRepair(AbstractSpookSingleShotRepairs):
    """Spook repairs that triggers that raises issues for obsolete YAML config."""

    domain = DOMAIN
    repair = "obsolete_platform_yaml_config"

    KNOWN_REMOVED_DOMAINS = {
        "aladdin_connect",
        "cert_expiry",
        "dlink",
        "dsmr_reader",
        "edl21",
        "generic",
        "imap",
        "kodi",
        "moon",
        "mqtt",
        "pushbullet",
        "radiotherm",
        "scrape",
        "season",
        "soundtouch",
        "tautulli",
        "uptime",
        "whois",
    }

    async def async_inspect(self) -> None:
        """Trigger a single shot repair."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        try:
            config = await async_hass_config_yaml(self.hass)
        except HomeAssistantError:
            LOGGER.exception("Failed to parse configuration.yaml")
            raise

        for platform in Platform:
            if platform not in config:
                continue
            for domain_config in config[platform]:
                if (
                    not (domain := domain_config.get("platform"))
                    or domain not in self.KNOWN_REMOVED_DOMAINS
                ):
                    continue

                self.async_create_issue(
                    issue_id=f"{platform}_{domain}",
                    translation_placeholders={
                        "platform": platform,
                        "domain": domain,
                    },
                )
                LOGGER.debug(
                    "Spook found a known invalid platform configured in the "
                    "YAML configuration and created an issue; "
                    "platform: %s, domain: %s",
                    platform,
                    domain,
                )
