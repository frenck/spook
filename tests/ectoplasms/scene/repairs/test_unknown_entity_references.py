"""Tests for the scene unknown entity references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.scene.repairs.unknown_entity_references import (
    SpookRepair,
)
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


def _mock_scene(unique_id: str | None) -> SimpleNamespace:
    """Return a mock Home Assistant scene entity."""
    return SimpleNamespace(
        entity_id="scene.movie_night",
        name="Movie Night",
        unique_id=unique_id,
        scene_config=SimpleNamespace(states={"light.ghost": {}}),
    )


@pytest.mark.parametrize(
    ("unique_id", "expected_edit_url"),
    [
        pytest.param("abc123", "/config/scene/edit/abc123", id="with_unique_id"),
        pytest.param(None, "/config/scene/dashboard", id="without_unique_id"),
    ],
)
async def test_issue_edit_url(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    unique_id: str | None,
    expected_edit_url: str,
) -> None:
    """Test the created issue links to the editor or the scene overview."""
    entities: dict[str, Any] = {"scene.movie_night": _mock_scene(unique_id)}
    hass.data["homeassistant_scene"] = SimpleNamespace(entities=entities)

    repair = SpookRepair(hass)
    await repair.async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        "scene_unknown_entity_references_scene.movie_night",
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["edit"] == expected_edit_url
    assert issue.translation_placeholders["entities"] == "- `light.ghost`"
