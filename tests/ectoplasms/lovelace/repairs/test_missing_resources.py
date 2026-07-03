"""Tests for the Lovelace missing resources repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

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


def _set_resources(hass: HomeAssistant, urls: list[str]) -> None:
    """Install a fake resource collection with the given URLs."""
    hass.data["lovelace"] = SimpleNamespace(
        resources=SimpleNamespace(
            async_items=lambda: [{"url": url, "type": "module"} for url in urls],
        ),
    )


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
