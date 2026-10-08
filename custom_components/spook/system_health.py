"""Spook - Your homie. What Spook tells System information about itself."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN
from .ectoplasms.spook.repair_issues import active_issues, is_ignored
from .integration_linking import sub_integration_links

if TYPE_CHECKING:
    from homeassistant.components import system_health
    from homeassistant.core import HomeAssistant


@callback
def async_register(
    _hass: HomeAssistant,
    register: system_health.SystemHealthRegistration,
) -> None:
    """Register what Spook shows under System information."""
    register.async_register_info(
        async_system_health_info,
        "/config/integrations/integration/spook",
    )


async def async_system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return the state of Spook, the things worth knowing in a bug report."""
    links = await hass.async_add_executor_job(sub_integration_links, hass)

    # Still there, but somebody told Spook to stop pointing them out.
    ghosts_ignored = sum(
        1
        for issue in ir.async_get(hass).issues.values()
        if issue.domain == DOMAIN and issue.active and is_ignored(issue)
    )
    ghosts_found = sum(1 for issue in active_issues(hass) if issue.domain == DOMAIN)

    return {
        "version": str(async_get_loaded_integration(hass, DOMAIN).version),
        "ghosts_found": ghosts_found,
        "ghosts_ignored": ghosts_ignored,
        "helpers_linked": f"{sum(links.values())} of {len(links)}",
    }
