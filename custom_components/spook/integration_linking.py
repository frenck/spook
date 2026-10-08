"""Spook - Your homie. Sub-integration symlinking helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def link_sub_integrations(hass: HomeAssistant) -> set[str]:
    """Link Spook sub integrations, and return the ones newly linked."""
    LOGGER.debug("Linking up Spook sub integrations")

    linked: set[str] = set()
    for manifest in Path(__file__).parent.rglob("integrations/*/manifest.json"):
        LOGGER.debug("Linking Spook sub integration: %s", manifest.parent.name)
        dest = Path(hass.config.config_dir) / "custom_components" / manifest.parent.name
        if not dest.exists():
            src = (
                Path(hass.config.config_dir)
                / "custom_components"
                / DOMAIN
                / "integrations"
                / manifest.parent.name
            )
            dest.symlink_to(src)
            linked.add(manifest.parent.name)
    return linked


def unlink_sub_integrations(hass: HomeAssistant) -> None:
    """Unlink Spook sub integrations."""
    LOGGER.debug("Unlinking Spook sub integrations")
    for manifest in Path(__file__).parent.rglob("integrations/*/manifest.json"):
        LOGGER.debug("Unlinking Spook sub integration: %s", manifest.parent.name)
        dest = Path(hass.config.config_dir) / "custom_components" / manifest.parent.name
        if dest.exists():
            dest.unlink()
