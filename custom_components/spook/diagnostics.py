"""Spook - Your homie. What Spook puts in a diagnostics download."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .ectoplasms.spook.repair_issues import is_ignored
from .integration_linking import sub_integration_links

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    _entry: ConfigEntry,
) -> dict[str, Any]:
    """Return what helps tracking down a Spook issue.

    Home Assistant adds the versions of itself and of Spook on its own. The
    names in a repair are left out: people paste this into public issues, and
    the ID and type of a repair are enough to go on.
    """
    links = await hass.async_add_executor_job(sub_integration_links, hass)

    return {
        "sub_integrations": {
            domain: {
                "linked": linked,
                "entries": [
                    {"state": entry.state.value, "disabled_by": entry.disabled_by}
                    for entry in hass.config_entries.async_entries(domain)
                ],
            }
            for domain, linked in links.items()
        },
        "repairs": [
            {
                "issue_id": issue.issue_id,
                "translation_key": issue.translation_key,
                "active": issue.active,
                "ignored": is_ignored(issue),
                "created": issue.created.isoformat(),
            }
            for issue in ir.async_get(hass).issues.values()
            if issue.domain == DOMAIN
        ],
    }
