"""Tests for the Lovelace missing resources repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.components.lovelace.resources import RESOURCE_STORAGE_KEY
from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.lovelace.repairs.missing_resources import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE_ID = "lovelace_missing_resources_lovelace_missing_resources"


def _make_www_file(hass: HomeAssistant, name: str) -> None:
    """Create a file under the config ``www`` directory."""
    www = Path(hass.config.path("www"))
    www.mkdir(parents=True, exist_ok=True)
    (www / name).write_text("// here", encoding="utf-8")


async def _no_loading_needed() -> dict[str, int]:
    """Stand in for the loading the real collection does on first use."""
    return {"resources": 0}


async def _no_deleting_needed(_item_id: str) -> None:
    """Stand in for the delete a storage-mode collection offers."""


def _set_resources(
    hass: HomeAssistant,
    urls: list[str],
    *,
    from_yaml: bool = False,
) -> None:
    """Install a fake resource collection with the given URLs.

    A storage-mode collection can delete an item and a YAML one cannot, which
    is the whole difference Spook goes on, so the fake has to carry it.
    """
    collection = SimpleNamespace(
        async_items=lambda: [{"url": url, "type": "module"} for url in urls],
        async_get_info=_no_loading_needed,
    )
    if not from_yaml:
        collection.async_delete_item = _no_deleting_needed

    hass.data["lovelace"] = SimpleNamespace(resources=collection)


async def test_missing_local_resource_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a local resource whose file is gone is reported."""
    await hass.async_add_executor_job(_make_www_file, hass, "present.js")

    _set_resources(
        hass,
        [
            "/local/present.js?v=1",
            "/local/gone.js",
            "/hacsfiles/removed-card/card.js",
            "https://cdn.example.com/external.js",
        ],
    )

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders
    # Present local file and external URL are not reported; the two missing
    # local files are.
    assert issue.translation_placeholders["resources"] == (
        "- `/hacsfiles/removed-card/card.js`\n- `/local/gone.js`"
    )


async def test_all_present_creates_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test present and external-only resources produce no issue."""
    await hass.async_add_executor_job(_make_www_file, hass, "here.js")

    _set_resources(hass, ["/local/here.js", "https://cdn.example.com/x.js"])

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_no_resource_collection_is_a_no_op(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a missing resource collection does not error."""
    hass.data["lovelace"] = SimpleNamespace(resources=None)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None


async def test_storage_resources_are_loaded_before_they_are_read(
    hass: HomeAssistant,
    hass_storage: dict,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the real resource collection is loaded rather than read empty.

    Storage-mode resources load the first time somebody asks for them, which
    is normally the dashboard, and Spook inspects long before that. Read
    straight, the collection is empty and a missing resource goes unreported.
    """
    hass_storage[RESOURCE_STORAGE_KEY] = {
        "version": 1,
        "key": RESOURCE_STORAGE_KEY,
        "data": {"items": [{"id": "1", "type": "module", "url": "/local/gone.js"}]},
    }
    assert await async_setup_component(hass, "lovelace", {})
    await hass.async_block_till_done()

    resources = hass.data["lovelace"].resources
    assert not resources.loaded, "core changed when it loads these"
    assert resources.async_items() == [], "and what an unloaded one holds"

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert "/local/gone.js" in issue.translation_placeholders["resources"]


async def test_stored_resources_point_at_the_resources_page(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test resources managed from the interface get the page to go to."""
    _set_resources(hass, ["/local/gone.js"])

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_key == "lovelace_missing_resources"


async def test_yaml_resources_are_told_where_the_file_is(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test resources listed in YAML are not sent to a page that cannot help.

    Nothing can delete a resource that came from the configuration, so the
    Resources page has nothing to offer somebody in this position.
    """
    _set_resources(hass, ["/local/gone.js"], from_yaml=True)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_key == "lovelace_missing_resources_yaml"
    # Same finding either way, so the list of what is missing must not differ.
    assert issue.translation_placeholders
    assert issue.translation_placeholders["resources"] == "- `/local/gone.js`"
