"""Tests for the Lovelace duplicate resources repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.components.lovelace.resources import RESOURCE_STORAGE_KEY
from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.lovelace.repairs.duplicate_resources import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE_ID = "lovelace_duplicate_resources_lovelace_duplicate_resources"


async def _no_loading_needed() -> dict[str, int]:
    """Stand in for the loading the real collection does on first use."""
    return {"resources": 0}


def _set_resources(hass: HomeAssistant, urls: list[str]) -> None:
    """Install a fake resource collection with the given URLs."""
    hass.data["lovelace"] = SimpleNamespace(
        resources=SimpleNamespace(
            async_items=lambda: [{"url": url, "type": "module"} for url in urls],
            async_get_info=_no_loading_needed,
        ),
    )


def _reported(issue_registry: ir.IssueRegistry) -> str | None:
    """Return the resource list the repair reported, if it raised one."""
    if (issue := issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)) is None:
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


async def test_running_before_lovelace_exists_is_a_no_op(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Lovelace is not always up when this runs.

    Repairs inspect the moment they activate, and again on every component
    that loads, with nobody checking which component it was. So this runs with
    no Lovelace in `hass.data` at all, where reaching straight for the key
    raises.
    """
    assert "lovelace" not in hass.data

    await SpookRepair(hass).async_inspect()

    assert _reported(issue_registry) is None
