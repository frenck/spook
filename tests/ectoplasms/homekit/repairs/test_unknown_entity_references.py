"""Tests for the HomeKit unknown entity references repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntryDisabler,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.entity_filtering import (
    async_setup_all_entity_ids_cache_invalidation,
)
from custom_components.spook.ectoplasms.homekit.repairs.unknown_entity_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


def _bridge(
    hass: HomeAssistant,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    source: str = SOURCE_USER,
    **kwargs: Any,
) -> MockConfigEntry:
    """Add a HomeKit bridge with an entity filter, the way HomeKit stores one.

    Only added, not set up: the repair reads the options, and setting HomeKit
    up for real would start a HomeKit server.
    """
    entry = MockConfigEntry(
        domain="homekit",
        title="HASS Bridge",
        source=source,
        options={
            "filter": {
                "include_domains": [],
                "include_entities": include or [],
                "exclude_domains": [],
                "exclude_entities": exclude or [],
            },
        },
        **kwargs,
    )
    entry.add_to_hass(hass)
    return entry


async def test_an_included_entity_that_is_gone_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a bridge including an entity that does not exist is reported."""
    hass.states.async_set("light.kitchen", "on")
    entry = _bridge(hass, include=["light.kitchen", "light.renamed_away"])

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(
        issue_registry, f"homekit_unknown_entity_references_{entry.entry_id}"
    )
    assert issue
    assert issue.translation_key == "homekit_unknown_entity_references"
    assert issue.translation_placeholders["bridge"] == "HASS Bridge"
    assert "light.renamed_away" in issue.translation_placeholders["entities"]
    assert "light.kitchen" not in issue.translation_placeholders["entities"]


async def test_an_excluded_entity_that_is_gone_is_reported_as_excluded(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an exclude that no longer matches anything is reported, marked.

    Renamed, the entity is not excluded any more and shows up in the Home
    app, which is the opposite of what the list asked for.
    """
    entry = _bridge(hass, exclude=["switch.renamed_away"])

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(
        issue_registry, f"homekit_unknown_entity_references_{entry.entry_id}"
    )
    assert issue
    assert (
        "`switch.renamed_away` (excluded)" in issue.translation_placeholders["entities"]
    )


async def test_a_bridge_naming_only_existing_entities_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test known entities, also those only in the registry, are not reported."""
    hass.states.async_set("light.kitchen", "on")
    entry = _bridge(hass, include=["light.kitchen"])

    await SpookRepair(hass).async_inspect()

    assert not async_issue_about(
        issue_registry, f"homekit_unknown_entity_references_{entry.entry_id}"
    )


async def test_a_bridge_from_yaml_says_to_edit_the_yaml(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a bridge set up in YAML gets the text that sends you there.

    HomeKit's own options flow turns an imported bridge away, so a link to
    Configure would lead nowhere.
    """
    entry = _bridge(hass, include=["light.renamed_away"], source=SOURCE_IMPORT)

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(
        issue_registry, f"homekit_unknown_entity_references_{entry.entry_id}"
    )
    assert issue
    assert issue.translation_key == "homekit_unknown_entity_references_yaml"


async def test_a_disabled_bridge_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a bridge that is turned off is not reported on."""
    entry = _bridge(
        hass, include=["light.renamed_away"], disabled_by=ConfigEntryDisabler.USER
    )

    await SpookRepair(hass).async_inspect()

    assert not async_issue_about(
        issue_registry, f"homekit_unknown_entity_references_{entry.entry_id}"
    )


async def test_an_entity_that_shows_up_late_clears_the_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entity arriving after the first look takes the issue away.

    Plenty of entities never touch the registry, and arrive as a state well
    after Home Assistant started.
    """
    # Spook keeps the known entity IDs cached, and forgets them when one
    # comes or goes. Without that, the second look sees the first one's list.
    async_setup_all_entity_ids_cache_invalidation(hass)
    entry = _bridge(hass, include=["sensor.late"])
    repair = SpookRepair(hass)

    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(
        issue_registry, f"homekit_unknown_entity_references_{entry.entry_id}"
    )

    hass.states.async_set("sensor.late", "1")
    await hass.async_block_till_done()
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert not async_issue_about(
        issue_registry, f"homekit_unknown_entity_references_{entry.entry_id}"
    )
    assert SpookRepair.inspect_on_entity_added_or_removed
