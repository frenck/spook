"""Spook - Your homie. What Spook puts in a diagnostics download."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .ectoplasms.spook.repair_issues import is_ignored
from .integration_linking import sub_integration_links
from .repairs import LookOutcome, SpookRepairManager

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .repairs import LastLook


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return what helps tracking down a Spook issue.

    Home Assistant adds the versions of itself and of Spook on its own. A
    repair is described by its type alone: people paste this into public
    issues, and both its placeholders and its ID can hold names, paths or
    URLs somebody chose.
    """
    links = await hass.async_add_executor_job(sub_integration_links, hass)

    return {
        "sub_integrations": {
            domain: {
                "linked": linked,
                "entries": [
                    {
                        "state": helper_entry.state.value,
                        "disabled_by": helper_entry.disabled_by,
                    }
                    for helper_entry in hass.config_entries.async_entries(domain)
                ],
            }
            for domain, linked in links.items()
        },
        "repairs": [
            {
                "translation_key": issue.translation_key,
                "active": issue.active,
                "ignored": is_ignored(issue),
                "created": issue.created.isoformat(),
            }
            for issue in ir.async_get(hass).issues.values()
            if issue.domain == DOMAIN
        ],
        "repair_setup": _repair_setup(entry),
    }


def _repair_setup(entry: ConfigEntry) -> dict[str, Any]:
    """Return how setting up the repairs went, and how each last looked.

    Spook sets its repairs up once Home Assistant has started, so until then
    there is nothing to tell. A repair is named by Spook's own name for it.
    """
    manager = getattr(entry, "runtime_data", None)
    if not isinstance(manager, SpookRepairManager):
        return {"state": "not_set_up", "modules": {}, "last_looks": {}}

    if not manager.set_up:
        return {
            "state": "waiting_for_home_assistant_to_start",
            "modules": {},
            "last_looks": {},
        }

    return {
        "state": "set_up",
        "modules": {
            module: state.value
            for module, state in sorted(manager.module_states.items())
        },
        "last_looks": {
            f"{repair.domain}.{repair.repair}": _look(repair.last_look)
            for repair in sorted(
                manager.repairs, key=lambda repair: (repair.domain, repair.repair)
            )
        },
    }


def _look(look: LastLook | None) -> dict[str, Any] | None:
    """Return a look, without anything a person chose.

    A failure is told by the type of its error alone. Its message can name an
    entity, a path or a URL. The reason a repair could not look is written by
    Spook, so that one is told as it is.
    """
    if look is None:
        return None

    described: dict[str, Any] = {
        "finished": look.finished.isoformat(),
        "outcome": look.outcome.value,
    }
    if look.outcome is LookOutcome.FAILED:
        described["error"] = look.detail
    elif look.outcome is LookOutcome.COULD_NOT_LOOK:
        described["reason"] = look.detail
    return described
