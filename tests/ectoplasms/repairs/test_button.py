"""Tests for the repairs ignore all and unignore all buttons."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir

from custom_components.spook.ectoplasms.repairs.button import (
    BUTTONS,
    RepairsSpookButtonEntity,
)
from tests.repair_helpers import async_add_config_entry, async_disable_config_entry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _raise(
    hass: HomeAssistant,
    issue_id: str,
    config_entry_id: str | None = None,
) -> None:
    """Report a repair issue, the way an integration would."""
    ir.async_create_issue(
        hass,
        "hue",
        issue_id,
        config_entry_id=config_entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=issue_id,
    )


def _ignored(hass: HomeAssistant) -> set[str]:
    """Return the IDs of the issues that are ignored."""
    return {
        issue.issue_id
        for issue in ir.async_get(hass).issues.values()
        if issue.dismissed_version is not None
    }


async def _press(hass: HomeAssistant, key: str) -> None:
    """Press one of the two buttons."""
    button = RepairsSpookButtonEntity(
        next(description for description in BUTTONS if description.key == key)
    )
    button.hass = hass
    await button.async_press()


async def test_both_leave_the_issues_of_a_disabled_entry_alone(
    hass: HomeAssistant,
) -> None:
    """All means all that the Repairs dashboard shows.

    Home Assistant hides the issues of a disabled config entry. Ignoring one
    nobody could see would keep it out of sight once the entry is enabled
    again, without anybody having looked at it.
    """
    entry = async_add_config_entry(hass, "hue")
    _raise(hass, "shown")
    _raise(hass, "hidden", entry.entry_id)
    _raise(hass, "hidden_and_ignored", entry.entry_id)
    ir.async_ignore_issue(hass, "hue", "hidden_and_ignored", ignore=True)
    await async_disable_config_entry(hass, entry)

    await _press(hass, "ignore_all")
    assert _ignored(hass) == {"shown", "hidden_and_ignored"}

    await _press(hass, "unignore_all")
    assert _ignored(hass) == {"hidden_and_ignored"}
