"""Tests for the Lovelace unknown area references repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from custom_components.spook.ectoplasms.lovelace.repairs.unknown_area_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

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

    issue = async_issue_about(
        issue_registry, "lovelace_unknown_area_references_lovelace"
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
        async_issue_about(issue_registry, "lovelace_unknown_area_references_lovelace")
        is None
    )


def _dashboard(url_path: str, config: dict[str, Any]) -> SimpleNamespace:
    """Return a stored dashboard with this config."""

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the dashboard config."""
        del force
        return config

    return SimpleNamespace(
        url_path=url_path, config={"title": url_path}, async_load=async_load
    )


async def test_areas_strategy_options_name_their_areas(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the areas dashboard's per-area options are checked by area ID.

    The frontend stores the areas dashboard as its strategy alone, no views,
    and keeps options per area under `areas_options`, keyed by area ID. An
    area removed since stays in there, and was never reported.
    """
    kitchen = area_registry.async_create("Kitchen")

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "dashboard-areas": _dashboard(
            "dashboard-areas",
            {
                "strategy": {
                    "type": "areas",
                    "areas_display": {"hidden": ["garage"], "order": [kitchen.id]},
                    "areas_options": {
                        kitchen.id: {"card_size": "small"},
                        "office": {"card_size": "small"},
                    },
                },
            },
        ),
    }

    await repair.async_inspect()

    issue = async_issue_about(
        issue_registry, "lovelace_unknown_area_references_dashboard-areas"
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["areas"] == "- `garage`\n- `office`"
    assert issue.translation_placeholders["edit"] == "/dashboard-areas/0?edit=1"


async def test_only_areas_strategies_key_options_by_area(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test nothing else near the areas options is read as an area.

    Floors are not areas, a card size is not one, and `areas_options` on
    anything but the areas strategies is somebody else's config.
    """
    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        "dashboard-areas": _dashboard(
            "dashboard-areas",
            {
                "strategy": {
                    "type": "areas",
                    "floors_display": {"order": ["ground_floor"]},
                    "areas_options": {},
                },
            },
        ),
        "lovelace": _dashboard(
            "lovelace",
            {
                "views": [
                    {
                        "cards": [
                            {
                                "type": "custom:some-card",
                                "areas_options": {"not_an_area": {}},
                            },
                        ],
                    },
                ],
            },
        ),
    }

    await repair.async_inspect()

    for url_path in ("dashboard-areas", "lovelace"):
        assert (
            async_issue_about(
                issue_registry, f"lovelace_unknown_area_references_{url_path}"
            )
            is None
        )
