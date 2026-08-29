"""Spook - Your homie. Reading dashboards without one bad one stopping the rest."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.lovelace.const import ConfigNotFound
from homeassistant.exceptions import HomeAssistantError

from ...const import LOGGER

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )

type Dashboard = LovelaceStorage | LovelaceYAML


async def async_dashboard_configs(
    dashboards: Mapping[str, Dashboard],
) -> AsyncIterator[tuple[Dashboard, str, dict[str, Any] | None]]:
    """Yield every dashboard, its URL path, and its config where there is one.

    A dashboard that cannot be read comes back with `None` rather than being
    skipped, so the caller still counts it among the things it looked at and
    can clean up issues it raised for it earlier.
    """
    for dashboard in dashboards.values():
        url_path = dashboard.url_path or "lovelace"

        try:
            config = await dashboard.async_load(force=False)
        except ConfigNotFound:
            LOGGER.debug("Config for dashboard %s not found, skipping", url_path)
            yield dashboard, url_path, None
        except HomeAssistantError:
            # A dashboard that will not load at all: broken YAML, or a secret
            # it cannot resolve. That is a problem of its own and not one
            # Spook reports on, but letting it out would stop every other
            # dashboard from being checked.
            LOGGER.warning(
                "Spook could not read dashboard %s, so it was skipped", url_path
            )
            yield dashboard, url_path, None
        else:
            yield dashboard, url_path, config
