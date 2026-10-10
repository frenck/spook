"""Tests for the Lovelace duplicate resources repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.components.lovelace.resources import RESOURCE_STORAGE_KEY
from homeassistant.helpers import collection
from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.lovelace.repairs.duplicate_resources import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


def _key(target: str, resource_type: str = "module") -> str:
    """Return the grouping key for a resource, which carries its type."""
    return f"{resource_type}|{target}"


def _issue_id(target: str, resource_type: str = "module") -> str:
    """Return the registry issue ID for one duplicated resource."""
    return f"lovelace_duplicate_resources_{_key(target, resource_type)}"


async def _no_loading_needed() -> dict[str, int]:
    """Stand in for the loading the real collection does on first use."""
    return {"resources": 0}


class _FakeStorageResources:
    """Stand-in for the storage-mode collection, which can delete.

    The YAML collection cannot, and the repair tells them apart by exactly
    that, so this one has to carry `async_delete_item` for the issues it
    produces to be fixable.
    """

    def __init__(self, urls: list[str], *, loaded: bool = True) -> None:
        """Hold one item per URL, in the order they were added."""
        self.items = [
            {"id": str(index), "url": url, "type": "module"}
            for index, url in enumerate(urls)
        ]
        self.loaded = loaded

    def async_items(self) -> list[dict]:
        """Return the items, empty until loaded, as the real one does."""
        return self.items if self.loaded else []

    async def async_get_info(self) -> dict[str, int]:
        """Load on first use, the way the real storage collection does."""
        self.loaded = True
        return {"resources": len(self.items)}

    async def async_delete_item(self, item_id: str) -> None:
        """Drop one item, raising what the real collection raises.

        `DictStorageCollection` raises `ItemNotFound`, which is a
        `HomeAssistantError` and not a `KeyError`, so anything catching the
        wrong one would look fine here and abort the flow in the house.
        """
        before = len(self.items)
        self.items = [item for item in self.items if item["id"] != item_id]
        if len(self.items) == before:
            raise collection.ItemNotFound(item_id)


def _set_resources(hass: HomeAssistant, urls: list[str]) -> _FakeStorageResources:
    """Install a fake storage resource collection with the given URLs."""
    resources = _FakeStorageResources(urls)
    hass.data["lovelace"] = SimpleNamespace(resources=resources)
    return resources


def _reported(
    issue_registry: ir.IssueRegistry,
    target: str = "",
    resource_type: str = "module",
) -> str | None:
    """Return what the repair reported for one resource, if it raised it."""
    if target:
        issue = issue_registry.async_get_issue(DOMAIN, _issue_id(target, resource_type))
    else:
        issues = [
            entry
            for entry in issue_registry.issues.values()
            if entry.translation_key == "lovelace_duplicate_resources"
        ]
        assert len(issues) <= 1, f"expected at most one issue, got {len(issues)}"
        issue = issues[0] if issues else None

    if issue is None:
        return None

    assert issue.translation_placeholders
    return issue.translation_placeholders["resources"]


async def test_the_same_url_twice_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Nothing stops this: core hands every resource a fresh random ID."""
    _set_resources(hass, ["/local/card.js", "/local/card.js", "/local/other.js"])

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry) == "- `/local/card.js`, listed 2 times"


async def test_a_local_file_behind_two_cache_busters_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The case that actually breaks a card.

    Updating a card by adding a resource for the new version leaves both. The
    browser treats the two URLs as different files and loads both, so the card
    registers itself twice and the second attempt throws.
    """
    _set_resources(hass, ["/local/card.js?v=1", "/local/card.js?v=2"])

    assert _reported(issue_registry) is None
    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry) == (
        "- `/local/card.js`, listed 2 times: `/local/card.js?v=1`, `/local/card.js?v=2`"
    )


async def test_an_external_url_with_a_different_query_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Somebody else's server may well serve two files from one path.

    A query string on a CDN can be a version that returns genuinely different
    content, so only an exact repeat counts there. Guessing otherwise would
    report a setup that is doing nothing wrong.
    """
    _set_resources(
        hass,
        [
            "https://cdn.example.com/lib.js?v=1",
            "https://cdn.example.com/lib.js?v=2",
        ],
    )

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry) is None


async def test_an_external_url_repeated_exactly_is_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The same URL twice is never intended, wherever it is served from."""
    _set_resources(
        hass,
        ["https://cdn.example.com/lib.js?v=1", "https://cdn.example.com/lib.js?v=1"],
    )

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry) == (
        "- `https://cdn.example.com/lib.js?v=1`, listed 2 times"
    )


async def test_it_counts_past_two(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Three versions of one card is the same mistake made twice."""
    _set_resources(
        hass, ["/local/card.js?v=1", "/local/card.js?v=2", "/local/card.js?v=3"]
    )

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry) == (
        "- `/local/card.js`, listed 3 times: `/local/card.js?v=1`, "
        "`/local/card.js?v=2`, `/local/card.js?v=3`"
    )


async def test_resources_that_differ_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An ordinary resource list has to stay quiet."""
    _set_resources(
        hass,
        [
            "/local/card.js",
            "/local/other.js?v=2",
            "/hacsfiles/some-card/some-card.js",
            "https://cdn.example.com/lib.js",
        ],
    )

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry) is None


async def test_no_resource_collection_is_a_no_op(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a missing resource collection does not error."""
    hass.data["lovelace"] = SimpleNamespace(resources=None)

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry) is None


async def test_storage_resources_are_loaded_before_they_are_read(
    hass: HomeAssistant,
    hass_storage: dict,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The real collection loads on first use, which is after Spook looks.

    Read straight it is empty, and a duplicate goes unreported.
    """
    hass_storage[RESOURCE_STORAGE_KEY] = {
        "version": 1,
        "key": RESOURCE_STORAGE_KEY,
        "data": {
            "items": [
                {"id": "1", "type": "module", "url": "/local/card.js?v=1"},
                {"id": "2", "type": "module", "url": "/local/card.js?v=2"},
            ]
        },
    }
    assert await async_setup_component(hass, "lovelace", {})
    await hass.async_block_till_done()

    resources = hass.data["lovelace"].resources
    assert not resources.loaded, "core changed when it loads these"
    assert resources.async_items() == [], "and what an unloaded one holds"

    await SpookRepair(hass).async_inspect()

    assert "/local/card.js" in (_reported(issue_registry) or "")


async def test_an_exact_repeat_is_named_the_way_it_is_listed(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A local resource is grouped by its path, with the query taken off.

    That key is not what is in the resource list when the URL carries a query,
    so reporting the key would send somebody looking for a URL that is not
    there.
    """
    _set_resources(hass, ["/local/card.js?v=1", "/local/card.js?v=1"])

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry) == "- `/local/card.js?v=1`, listed 2 times"


async def test_each_duplicated_resource_gets_its_own_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """One issue per resource, so they can be dealt with one at a time."""
    _set_resources(
        hass,
        [
            "/local/one.js?v=1",
            "/local/one.js?v=2",
            "/local/two.js",
            "/local/two.js",
            "/local/fine.js",
        ],
    )

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry, "/local/one.js")
    assert _reported(issue_registry, "/local/two.js")
    assert _reported(issue_registry, "/local/fine.js") is None


async def test_the_issue_is_fixable_and_carries_what_the_flow_needs(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The flow is dispatched on this data key, so it has to be there."""
    _set_resources(hass, ["/local/card.js?v=1", "/local/card.js?v=2"])

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id("/local/card.js"))
    assert issue
    assert issue.is_fixable
    assert issue.data == {
        "duplicate_resource_url": _key("/local/card.js"),
        "resource": "/local/card.js",
        "resources": (
            "- `/local/card.js`, listed 2 times: `/local/card.js?v=1`, "
            "`/local/card.js?v=2`"
        ),
        "count": "2",
    }


def test_lovelace_is_a_hard_dependency() -> None:
    """Both resource repairs read `hass.data["lovelace"]` without a guard.

    That is only safe because Home Assistant sets up a hard dependency before
    the integration that declares it. Moving Lovelace to `after_dependencies`,
    or dropping it, makes those reads a crash, so this is the thing holding
    them up.
    """
    manifest = json.loads(
        (
            Path(__file__).parents[4] / "custom_components" / "spook" / "manifest.json"
        ).read_text()
    )

    assert "lovelace" in manifest["dependencies"]


async def test_a_yaml_resource_is_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A duplicate is a duplicate wherever the resources are configured.

    The fix flow is what works out that it cannot delete these; the repair
    reports them either way, so nobody is left without the finding.
    """
    hass.data["lovelace"] = SimpleNamespace(
        resources=SimpleNamespace(
            async_items=lambda: [
                {"url": "/local/card.js?v=1", "type": "module"},
                {"url": "/local/card.js?v=2", "type": "module"},
            ],
            async_get_info=_no_loading_needed,
        ),
    )

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id("/local/card.js"))
    assert issue
    assert issue.is_fixable


def test_the_issue_has_a_fix_flow_and_not_a_description() -> None:
    """Home Assistant treats those two as mutually exclusive.

    Carrying both fails hassfest with "two or more values in the same group of
    exclusion 'fixable'", which is how the YAML case ended up handled inside
    the flow rather than by a second block of text.
    """
    strings = json.loads(
        (
            Path(__file__).parents[4]
            / "custom_components"
            / "spook"
            / "translations"
            / "en.json"
        ).read_text()
    )
    block = strings["issues"]["lovelace_duplicate_resources"]

    assert "fix_flow" in block
    assert "description" not in block
    assert "yaml" in block["fix_flow"]["abort"]


async def test_the_same_url_under_two_types_is_not_a_repeat(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Home Assistant loads a `module` differently from a `css`.

    So the same URL under two types is two instructions, not one repeated.
    Reporting it would be bad enough on its own; the fix flow clears all but
    one, so it would take away something that was meant to be there.
    """
    hass.data["lovelace"] = SimpleNamespace(
        resources=_FakeStorageResources([]),
    )
    hass.data["lovelace"].resources.items = [
        {"id": "1", "url": "/local/thing", "type": "module"},
        {"id": "2", "url": "/local/thing", "type": "css"},
    ]

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry) is None


async def test_a_repeat_within_one_type_is_still_caught(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The type being part of the identity must not lose the real case."""
    hass.data["lovelace"] = SimpleNamespace(
        resources=_FakeStorageResources([]),
    )
    hass.data["lovelace"].resources.items = [
        {"id": "1", "url": "/local/thing", "type": "module"},
        {"id": "2", "url": "/local/thing", "type": "css"},
        {"id": "3", "url": "/local/thing", "type": "css"},
    ]

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry, "/local/thing", "css")
    assert _reported(issue_registry, "/local/thing", "module") is None
