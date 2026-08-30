"""Tests for the duplicate dashboard resource fix flow."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir

from custom_components.spook.const import DOMAIN
from custom_components.spook.repairs import (
    DuplicateResourceFixFlow,
    async_create_fix_flow,
)

from .test_duplicate_resources import _FakeStorageResources

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _flow(hass: HomeAssistant, key: str) -> DuplicateResourceFixFlow:
    """Return the flow, wired the way the repairs component wires it."""
    flow = DuplicateResourceFixFlow()
    flow.hass = hass
    flow.issue_id = f"lovelace_duplicate_resources_{key}"
    flow.data = {"duplicate_resource_url": key, "resource": key}
    return flow


def _urls(resources: _FakeStorageResources) -> list[str]:
    """Return the URLs still listed."""
    return [item["url"] for item in resources.async_items()]


async def test_the_flow_is_chosen_for_this_issue(hass: HomeAssistant) -> None:
    """Dispatch is on the data key, so this is what wires the two together."""
    flow = await async_create_fix_flow(
        hass,
        "lovelace_duplicate_resources_/local/card.js",
        {"duplicate_resource_url": "/local/card.js"},
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

    await _flow(hass, "/local/card.js").async_step_remove()

    assert _urls(resources) == ["/local/card.js?v=2", "/local/other.js"]


async def test_removing_clears_every_extra_copy(hass: HomeAssistant) -> None:
    """Three copies means two to clear, not one."""
    resources = _FakeStorageResources(
        ["/local/card.js?v=1", "/local/card.js?v=2", "/local/card.js?v=3"]
    )
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    await _flow(hass, "/local/card.js").async_step_remove()

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

    await _flow(hass, "/local/card.js").async_step_remove()

    assert _urls(resources) == [
        "/local/card.js?v=2",
        "/local/keep.js?v=1",
        "/local/keep.js?v=2",
    ]


async def test_removing_something_already_gone_still_finishes(
    hass: HomeAssistant,
) -> None:
    """Somebody clearing it themselves first is a fine way for this to end."""
    resources = _FakeStorageResources(["/local/card.js?v=2"])
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    result = await _flow(hass, "/local/card.js").async_step_remove()

    assert result["type"] == "create_entry"
    assert _urls(resources) == ["/local/card.js?v=2"]


async def test_removing_without_lovelace_still_finishes(hass: HomeAssistant) -> None:
    """The flow can be opened long after the resources went away."""
    assert "lovelace" not in hass.data

    result = await _flow(hass, "/local/card.js").async_step_remove()

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
        "lovelace_duplicate_resources_/local/card.js",
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="lovelace_duplicate_resources",
    )

    result = await _flow(hass, "/local/card.js").async_step_ignore()

    assert result["type"] == "abort"
    issue = issue_registry.async_get_issue(
        DOMAIN, "lovelace_duplicate_resources_/local/card.js"
    )
    assert issue
    assert issue.dismissed_version is not None
    # Nothing was cleared: ignoring is not fixing.
    assert _urls(resources) == ["/local/card.js?v=1", "/local/card.js?v=2"]


async def test_managing_it_yourself_leaves_everything(hass: HomeAssistant) -> None:
    """Aborting keeps the issue, so it stays until actually resolved."""
    resources = _FakeStorageResources(["/local/card.js?v=1", "/local/card.js?v=2"])
    hass.data["lovelace"] = SimpleNamespace(resources=resources)

    result = await _flow(hass, "/local/card.js").async_step_manage()

    assert result["type"] == "abort"
    assert result["reason"] == "manage"
    assert _urls(resources) == ["/local/card.js?v=1", "/local/card.js?v=2"]
