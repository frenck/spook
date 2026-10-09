"""Tests for the documentation each repair links to."""

from __future__ import annotations

import importlib
from pathlib import Path
import re
from typing import TYPE_CHECKING

import pytest

from homeassistant.helpers import issue_registry as ir

from custom_components.spook import repairs
from custom_components.spook.const import DOMAIN
from custom_components.spook.repair_documentation import (
    REPAIR_DOCUMENTATION,
    repair_documentation_url,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

SPOOK = Path(repairs.__file__).parent
DOCUMENTATION = SPOOK.parent.parent / "documentation" / "integrations"


def _repair_modules() -> list[str]:
    """Return every repair module, found the way Spook finds them."""
    return sorted(
        str(path.relative_to(SPOOK).with_suffix("")).replace("/", ".")
        for path in SPOOK.glob("ectoplasms/*/repairs/*.py")
        if path.name != "__init__.py"
    )


def _repairs() -> dict[str, type[repairs.AbstractSpookRepair]]:
    """Return every repair by its name."""
    found = {}
    for module_name in _repair_modules():
        module = importlib.import_module(f"custom_components.spook.{module_name}")
        found[module.SpookRepair.repair] = module.SpookRepair
    return found


def _anchor(heading: str) -> str:
    """Return the anchor the documentation gives a heading."""
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


def _repair_anchors(page: str) -> set[str]:
    """Return the anchors of the headings in a page's Repairs section."""
    anchors = set()
    in_repairs = False
    for line in (
        (DOCUMENTATION / f"{page.replace('-', '_')}.md").read_text().splitlines()
    ):
        if line.startswith("## "):
            in_repairs = line == "## Repairs"
        elif in_repairs and line.startswith("### "):
            anchors.add(_anchor(line.removeprefix("### ")))
    return anchors


def test_every_repair_links_to_its_documentation() -> None:
    """Test no repair is left without, and no entry outlives its repair."""
    assert set(REPAIR_DOCUMENTATION) == set(_repairs())


@pytest.mark.parametrize(
    ("repair", "page_and_anchor"), sorted(REPAIR_DOCUMENTATION.items())
)
def test_documentation_has_the_heading(repair: str, page_and_anchor: str) -> None:
    """Test each link leads to a heading that is there.

    A renamed heading moves its anchor, and the link would then land at the
    top of the page instead of at the repair.
    """
    page, anchor = page_and_anchor.split("#")

    assert anchor in _repair_anchors(page), repair


async def test_issue_carries_the_documentation(hass: HomeAssistant) -> None:
    """Test an issue a repair raises links to where that repair is explained."""
    repair = _repairs()["empty_areas"](hass)

    repair.async_create_issue(issue_id="attic")

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "empty_areas_attic")
    assert issue is not None
    assert issue.learn_more_url == "https://spook.boo/homeassistant#empty-areas"


def test_unknown_repair_has_no_documentation() -> None:
    """Test a repair without an entry gets no link, rather than a wrong one."""
    assert repair_documentation_url("not_a_repair") is None
