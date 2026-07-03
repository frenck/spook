"""Tests for the Lovelace repair's dashboard-level entity extraction.

The repair maps each referenced entity to the view it appears in, for the
issue's edit link. The generic per-node extraction itself is covered by
``tests/test_dashboard_extraction.py``; these tests cover the repair's
view-path bookkeeping on top of it.
"""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any


from custom_components.spook.ectoplasms.lovelace.repairs.unknown_entity_references import (
    SpookRepair,
)
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture(name="repair")
def repair_fixture(hass: HomeAssistant) -> SpookRepair:
    """Return a ``SpookRepair`` instance wired up to the test ``hass``."""
    return SpookRepair(hass)


def _extract(repair: SpookRepair, config: dict[str, Any]) -> dict[str, int | str]:
    """Call the name-mangled dashboard-level extractor."""
    return repair._SpookRepair__async_extract_entities(config)  # noqa: SLF001  # type: ignore[attr-defined]


def test_dashboard_with_no_views_returns_empty(repair: SpookRepair) -> None:
    """A dashboard with no ``views`` key yields no entities."""
    assert _extract(repair, {}) == {}


def test_dashboard_non_dict_returns_empty(repair: SpookRepair) -> None:
    """A non-dict config yields no entities."""
    assert _extract(repair, "not a dict") == {}  # type: ignore[arg-type]


def test_dashboard_full_walk(repair: SpookRepair) -> None:
    """Views, badges, cards, and sections are all walked with their view path."""
    config = {
        "views": [
            {
                "title": "Home",
                "path": "home",
                "badges": [{"entity": "sensor.outside_temperature"}],
                "cards": [{"type": "entity", "entity": "light.kitchen"}],
                "sections": [{"cards": [{"type": "entity", "entity": "switch.lamp"}]}],
            }
        ]
    }
    assert _extract(repair, config) == {
        "sensor.outside_temperature": "home",
        "light.kitchen": "home",
        "switch.lamp": "home",
    }


def test_dashboard_uses_view_index_when_path_is_missing(repair: SpookRepair) -> None:
    """A view without a path falls back to its index."""
    config = {
        "views": [
            {"title": "Home", "cards": [{"type": "entity", "entity": "light.kitchen"}]},
            {"title": "Second", "cards": [{"type": "entity", "entity": "switch.lamp"}]},
        ]
    }
    assert _extract(repair, config) == {
        "light.kitchen": 0,
        "switch.lamp": 1,
    }


def test_dashboard_uses_view_index_when_path_is_empty(repair: SpookRepair) -> None:
    """An empty view path falls back to its index."""
    config = {
        "views": [
            {
                "path": "",
                "cards": [{"type": "entity", "entity": "light.kitchen"}],
            },
            "not a view",
            {
                "path": None,
                "cards": [{"type": "entity", "entity": "switch.lamp"}],
            },
        ]
    }
    assert _extract(repair, config) == {
        "light.kitchen": 0,
        "switch.lamp": 2,
    }


def test_dashboard_keeps_first_view_for_duplicate_entity(repair: SpookRepair) -> None:
    """A duplicate entity keeps the first view path by dashboard order."""
    config = {
        "views": [
            {"path": "first", "cards": [{"type": "entity", "entity": "light.kitchen"}]},
            {
                "path": "second",
                "cards": [{"type": "entity", "entity": "light.kitchen"}],
            },
        ]
    }
    assert _extract(repair, config) == {"light.kitchen": "first"}


def test_dashboard_splits_comma_separated_entities_per_view(
    repair: SpookRepair,
) -> None:
    """Comma-separated entity IDs keep the source view path."""
    config = {
        "views": [
            {
                "path": "home",
                "cards": [
                    {"type": "entity", "entity": "light.kitchen, switch.lamp"},
                ],
            }
        ]
    }
    assert _extract(repair, config) == {
        "light.kitchen": "home",
        "switch.lamp": "home",
    }


async def test_inspect_sorts_unknown_entities_in_issue_placeholder(
    repair: SpookRepair,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repair message lists unknown entities in a stable order."""

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Load the dashboard config."""
        del force
        return {
            "views": [
                {
                    "path": "home",
                    "cards": [
                        {"type": "entity", "entity": "switch.z"},
                        {"type": "entity", "entity": "light.a"},
                    ],
                }
            ]
        }

    captured: dict[str, Any] = {}

    def async_create_issue(**kwargs: Any) -> None:
        """Capture the created issue."""
        captured.update(kwargs)

    repair._dashboards = {  # noqa: SLF001
        "lovelace": SimpleNamespace(
            url_path="lovelace",
            config={"title": "Overview"},
            async_load=async_load,
        )
    }
    monkeypatch.setattr(repair, "async_create_issue", async_create_issue)

    await repair.async_inspect()

    assert captured["translation_placeholders"]["entities"] == (
        "- `light.a`\n- `switch.z`"
    )


def test_dashboard_covers_custom_card_structures(repair: SpookRepair) -> None:
    """Entities buried in a custom card structure are now reached.

    The old per-card walker only recursed into known shapes; the generic
    walker finds references anywhere.
    """
    config = {
        "views": [
            {
                "path": "home",
                "cards": [
                    {
                        "type": "custom:fancy-card",
                        "rows": [{"widget": {"entity": "sensor.custom"}}],
                    },
                ],
            }
        ]
    }
    assert _extract(repair, config) == {"sensor.custom": "home"}
