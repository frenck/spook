"""Tests for repair issue edit URLs."""
# ruff: noqa: SLF001
# pylint: disable=protected-access

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from custom_components.spook.repairs import (
    AbstractSpookEntityComponentUnknownReferencesRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class _UnavailableEntity:  # pylint: disable=too-few-public-methods
    """Marker class for unavailable entities."""


class MockReferencesRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Mock unknown-references repair."""

    domain = "automation"
    repair = "mock_repair"
    unavailable_entity_class = _UnavailableEntity
    entity_label = "automation"
    reference_label = "entities"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return no unknown references."""
        del entity
        return set()


def test_edit_url_with_unique_id(hass: HomeAssistant) -> None:
    """Test the edit URL deep-links to the editor when a unique ID exists."""
    repair = MockReferencesRepair(hass)

    assert (
        repair._edit_url(SimpleNamespace(unique_id="abc123"))
        == "/config/automation/edit/abc123"
    )


def test_edit_url_without_unique_id(hass: HomeAssistant) -> None:
    """Test the edit URL falls back to the overview without a unique ID.

    Automations and scenes created in YAML without an ``id:`` have no unique
    ID and no editor to deep-link to.
    """
    repair = MockReferencesRepair(hass)

    assert (
        repair._edit_url(SimpleNamespace(unique_id=None))
        == "/config/automation/dashboard"
    )
