"""Tests for template extraction from configurations."""

# ruff: noqa: SLF001
# pylint: disable=protected-access

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from custom_components.spook import template_extraction
from custom_components.spook.template_extraction import (
    async_extract_entities_from_config,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    import pytest


async def test_entities_are_extracted_from_config_templates(
    hass: HomeAssistant,
) -> None:
    """Test the entities a configuration's templates name are found."""
    config = {
        "condition": "template",
        "value_template": "{{ states('light.kitchen') }}",
    }

    assert await async_extract_entities_from_config(
        hass, config, known_services=set()
    ) == {"light.kitchen"}


async def test_config_extraction_runs_in_the_executor(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test walking and lexing a configuration happens off the event loop.

    The extraction is pure computation over plain data, and a large
    configuration holds a lot of it. Running it on the event loop stalls
    everything else Home Assistant is doing, so it is handed to the
    executor instead.
    """
    loop_thread = threading.get_ident()
    ran_on: list[int] = []
    real_extract = template_extraction._extract_entities_from_config

    def _spying_extract(
        config: Any,
        known_services: set[str],
        shadowed: frozenset[str] = frozenset(),
    ) -> set[str]:
        ran_on.append(threading.get_ident())
        return real_extract(config, known_services, shadowed)

    monkeypatch.setattr(
        template_extraction, "_extract_entities_from_config", _spying_extract
    )

    config = {
        "condition": "template",
        "value_template": "{{ states('light.kitchen') }}",
    }
    result = await async_extract_entities_from_config(
        hass, config, known_services=set()
    )

    assert result == {"light.kitchen"}
    assert ran_on
    assert ran_on[0] != loop_thread
