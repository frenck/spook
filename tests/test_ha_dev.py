"""Tests for the restore cache helpers the Home Assistant dev canary swaps in."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import State
from pytest_homeassistant_custom_component import common
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_mock_restore_cache_refuses_duplicate_entity_ids(
    hass: HomeAssistant,
) -> None:
    """A duplicate would be dropped silently, so the fixture would differ."""
    with pytest.raises(AssertionError, match="Duplicate entity_id"):
        common.mock_restore_cache(
            hass, [State("light.kitchen", "on"), State("light.kitchen", "off")]
        )
