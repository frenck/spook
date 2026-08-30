"""Tests for the duplicate dashboard resource fix flow."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.helpers import collection, issue_registry as ir

from custom_components.spook.const import DOMAIN
from custom_components.spook.repairs import (
    DuplicateResourceFixFlow,
    async_create_fix_flow,
)

from .test_duplicate_resources import _FakeStorageResources, _key

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _flow(hass: HomeAssistant, key: str) -> DuplicateResourceFixFlow:
    """Return the flow, wired the way the repairs component wires it."""
    flow = DuplicateResourceFixFlow()
    flow.hass = hass
    flow.issue_id = f"lovelace_duplicate_resources_{key}"
    flow.data = {"duplicate_resource_url": key, "resource": key.split("|", 1)[-1]}
    return flow


def _urls(resources: _FakeStorageResources) -> list[str]:
    """Return the URLs still listed."""
    return [item["url"] for item in resources.async_items()]


async def test_the_flow_is_chosen_for_this_issue(hass: HomeAssistant) -> None:
    """Dispatch is on the data key, so this is what wires the two together."""
    flow = await async_create_fix_flow(
        hass,
        f"lovelace_duplicate_resources_{_key('/local/card.js')}",
        {"duplicate_resource_url": _key("/local/card.js")},
    )

    assert isinstance(flow, DuplicateResourceFixFlow)


async def test_removing_keeps_the_most_recently_added(hass: HomeAssistant) -> None:
    """The newest copy is the one somebody meant to end up with.

    A card updated by adding a resource for the new version leaves the old one
    above it, so keeping the last is keeping the version they installed.
    """
    resources = _FakeStorageResources(
        ["/local/card.js?v=1", "/local/card.js?v=2", "/local/other.js"]
    )
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    await _flow(hass, _key("/local/card.js")).async_step_remove()

    assert _urls(resources) == ["/local/card.js?v=2", "/local/other.js"]


async def test_removing_clears_every_extra_copy(hass: HomeAssistant) -> None:
    """Three copies means two to clear, not one."""
    resources = _FakeStorageResources(
        ["/local/card.js?v=1", "/local/card.js?v=2", "/local/card.js?v=3"]
    )
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    await _flow(hass, _key("/local/card.js")).async_step_remove()

    assert _urls(resources) == ["/local/card.js?v=3"]


async def test_removing_leaves_other_resources_alone(hass: HomeAssistant) -> None:
    """Only the resource the issue is about is touched."""
    resources = _FakeStorageResources(
        [
            "/local/card.js?v=1",
            "/local/card.js?v=2",
            "/local/keep.js?v=1",
            "/local/keep.js?v=2",
        ]
    )
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    await _flow(hass, _key("/local/card.js")).async_step_remove()

    assert _urls(resources) == [
        "/local/card.js?v=2",
        "/local/keep.js?v=1",
        "/local/keep.js?v=2",
    ]


class _RacyResources(_FakeStorageResources):
    """A collection where one copy vanishes before the flow reaches it."""

    def __init__(self, urls: list[str], *, vanishing: str) -> None:
        """Remember which item ID somebody else is about to remove."""
        super().__init__(urls)
        self._vanishing = vanishing

    async def async_delete_item(self, item_id: str) -> None:
        """Raise for the vanished one, the way the real collection would."""
        if item_id == self._vanishing:
            raise collection.ItemNotFound(item_id)
        await super().async_delete_item(item_id)


async def test_a_copy_removed_underneath_the_flow_does_not_stop_it(
    hass: HomeAssistant,
) -> None:
    """The copies to clear are worked out first, then removed one at a time.

    Somebody removing one in between is a fine way for this to end, but only
    if the right exception is caught: the collection raises `ItemNotFound`,
    which is a `HomeAssistantError` and not a `KeyError`.
    """
    resources = _RacyResources(
        ["/local/card.js?v=1", "/local/card.js?v=2", "/local/card.js?v=3"],
        vanishing="0",
    )
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    result = await _flow(hass, _key("/local/card.js")).async_step_remove()

    assert result["type"] == "create_entry"
    # The one that vanished is still listed here, because this fake only
    # refuses to delete it. The point is that v=2 was still cleared after it.
    assert _urls(resources) == ["/local/card.js?v=1", "/local/card.js?v=3"]


async def test_removing_when_there_is_nothing_left_to_remove_still_finishes(
    hass: HomeAssistant,
) -> None:
    """Somebody clearing them all themselves first is a fine ending too."""
    resources = _FakeStorageResources(["/local/card.js?v=2"])
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    result = await _flow(hass, _key("/local/card.js")).async_step_remove()

    assert result["type"] == "create_entry"
    assert _urls(resources) == ["/local/card.js?v=2"]


async def test_removing_without_lovelace_still_finishes(hass: HomeAssistant) -> None:
    """The flow can be opened long after the resources went away."""
    assert "lovelace" not in hass.data

    result = await _flow(hass, _key("/local/card.js")).async_step_remove()

    assert result["type"] == "create_entry"


async def test_ignoring_keeps_the_issue_so_the_ignore_sticks(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A completed flow deletes the issue, and it would come straight back."""
    resources = _FakeStorageResources(["/local/card.js?v=1", "/local/card.js?v=2"])
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    issue_registry.async_get_or_create(
        DOMAIN,
        f"lovelace_duplicate_resources_{_key('/local/card.js')}",
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="lovelace_duplicate_resources",
    )

    result = await _flow(hass, _key("/local/card.js")).async_step_ignore()

    assert result["type"] == "abort"
    issue = issue_registry.async_get_issue(
        DOMAIN, f"lovelace_duplicate_resources_{_key('/local/card.js')}"
    )
    assert issue
    assert issue.dismissed_version is not None
    # Nothing was cleared: ignoring is not fixing.
    assert _urls(resources) == ["/local/card.js?v=1", "/local/card.js?v=2"]


async def test_managing_it_yourself_leaves_everything(hass: HomeAssistant) -> None:
    """Aborting keeps the issue, so it stays until actually resolved."""
    resources = _FakeStorageResources(["/local/card.js?v=1", "/local/card.js?v=2"])
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    result = await _flow(hass, _key("/local/card.js")).async_step_manage()

    assert result["type"] == "abort"
    assert result["reason"] == "manage"
    assert _urls(resources) == ["/local/card.js?v=1", "/local/card.js?v=2"]


async def test_removing_from_a_cold_collection_still_clears(
    hass: HomeAssistant,
) -> None:
    """A storage collection hands out nothing until it has been loaded.

    Read cold it looks empty, so the flow would clear nothing and still report
    that it had, which is the worst of the available outcomes.
    """
    resources = _FakeStorageResources(
        ["/local/card.js?v=1", "/local/card.js?v=2"], loaded=False
    )
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    await _flow(hass, _key("/local/card.js")).async_step_remove()

    assert _urls(resources) == ["/local/card.js?v=2"]


async def test_a_yaml_collection_is_told_where_the_file_is(
    hass: HomeAssistant,
) -> None:
    """Nothing can delete a YAML resource, so the menu would be a lie.

    Offering "clear the extra copies" against a static list is a button that
    quietly does nothing, so this aborts with the file to edit instead.
    """
    hass.data["lovelace"] = SimpleNamespace(
        resources=SimpleNamespace(
            async_items=lambda: [
                {"url": "/local/card.js?v=1", "type": "module"},
                {"url": "/local/card.js?v=2", "type": "module"},
            ],
        ),
    )

    result = await _flow(hass, _key("/local/card.js")).async_step_init()

    assert result["type"] == "abort"
    assert result["reason"] == "yaml"
    assert result["description_placeholders"]["resource"] == "/local/card.js"


async def test_a_storage_collection_still_gets_the_menu(
    hass: HomeAssistant,
) -> None:
    """The abort above must not swallow the case it was added beside."""
    resources = _FakeStorageResources(["/local/card.js?v=1", "/local/card.js?v=2"])
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    result = await _flow(hass, _key("/local/card.js")).async_step_init()

    assert result["type"] == "menu"
    assert set(result["menu_options"]) == {"remove", "manage", "ignore"}


class _VanishingNewest(_FakeStorageResources):
    """Somebody removes the copy this was going to keep, mid-clear."""

    def __init__(self, urls: list[str]) -> None:
        """Start out with nobody having interfered yet."""
        super().__init__(urls)
        self._interfered = False

    async def async_delete_item(self, item_id: str) -> None:
        """Delete as asked, then take the newest away the first time."""
        await super().async_delete_item(item_id)
        if not self._interfered:
            self._interfered = True
            self.items = self.items[:-1]


async def test_it_stops_when_somebody_takes_the_kept_copy_away(
    hass: HomeAssistant,
) -> None:
    """Deleting awaits, so the list can change underneath this.

    Against a snapshot taken once, losing the copy meant to be kept means
    every copy gets cleared and the card stops loading at all. Working it out
    again after each deletion leaves whatever is still there.
    """
    resources = _VanishingNewest(
        ["/local/card.js?v=1", "/local/card.js?v=2", "/local/card.js?v=3"]
    )
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    await _flow(hass, _key("/local/card.js")).async_step_remove()

    # v=1 cleared, v=3 taken by the other client, and v=2 left alone rather
    # than cleared on the strength of a list that no longer described anything.
    assert _urls(resources) == ["/local/card.js?v=2"]
