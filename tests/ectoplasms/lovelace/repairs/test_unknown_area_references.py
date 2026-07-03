"""Tests for the Lovelace unknown area references repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.lovelace.repairs.unknown_area_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import area_registry as ar, issue_registry as ir


def _extract(repair: SpookRepair, config: dict[str, Any]) -> dict[str, int | str]:
    """Call the name-mangled dashboard-level area extractor."""
    return repair._SpookRepair__async_extract_areas(config)  # noqa: SLF001  # type: ignore[attr-defined]


def test_extract_areas_keeps_first_view_path(hass: HomeAssistant) -> None:
    """Test each area is mapped to the first view it appears in."""
    repair = SpookRepair(hass)
    config = {
        "views": [
            {"path": "home", "cards": [{"type": "area", "area": "kitchen"}]},
            {"path": "second", "cards": [{"type": "area", "area": "kitchen"}]},
        ],
    }

    assert _extract(repair, config) == {"kitchen": "home"}


async def test_unknown_area_creates_issue(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a dashboard referencing a nonexistent area is reported."""
    known = area_registry.async_create("Living Room")

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the dashboard config."""
        del force
        return {
            "views": [
                {
                    "path": "home",
                    "cards": [
                        {"type": "area", "area": known.id},
                        {"type": "area", "area": "ghost_area"},
                    ],
                },
            ],
        }

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": SimpleNamespace(
            url_path="lovelace",
            config={"title": "Overview"},
            async_load=async_load,
        ),
    }

    await repair.async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        "lovelace_unknown_area_references_lovelace",
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["areas"] == "- `ghost_area`"
    assert issue.translation_placeholders["edit"] == "/lovelace/home?edit=1"


async def test_known_areas_create_no_issue(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a dashboard referencing only existing areas is not reported."""
    known = area_registry.async_create("Kitchen")

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the dashboard config."""
        del force
        return {"views": [{"cards": [{"type": "area", "area": known.id}]}]}

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "lovelace": SimpleNamespace(
            url_path="lovelace",
            config=None,
            async_load=async_load,
        ),
    }

    await repair.async_inspect()

    assert (
        issue_registry.async_get_issue(
            DOMAIN,
            "lovelace_unknown_area_references_lovelace",
        )
        is None
    )
