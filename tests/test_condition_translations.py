"""Tests for Spook condition descriptors and translations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from custom_components.spook.condition import async_get_conditions, translation_key

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

SPOOK_ROOT = Path(__file__).parents[1] / "custom_components" / "spook"


def _descriptors() -> dict:
    """Return the condition descriptors."""
    return yaml.safe_load((SPOOK_ROOT / "conditions.yaml").read_text())


def _translations() -> dict:
    """Return the English condition translations."""
    return json.loads((SPOOK_ROOT / "translations" / "en.json").read_text())[
        "conditions"
    ]


async def test_every_condition_has_a_descriptor(hass: HomeAssistant) -> None:
    """Test every discovered condition is described in conditions.yaml."""
    assert set(await async_get_conditions(hass)) == set(_descriptors())


def test_every_condition_has_translations() -> None:
    """Test every described condition has a matching translation.

    A condition keyed for another integration's domain cannot use that key in
    Spook's own translation file, so it is filed under `domain_name`, the same
    shape the actions use. The mapping comes from the code doing the injecting,
    so this checks the real convention rather than a copy of it.
    """
    assert {translation_key(key) for key in _descriptors()} == set(_translations())


def test_every_condition_field_has_translations() -> None:
    """Test every described condition field has a matching translation.

    A field without a translation renders as its raw key in the UI, which is
    the kind of thing nobody notices until a user screenshots it.
    """
    translations = _translations()

    for condition, descriptor in _descriptors().items():
        described = set(descriptor.get("fields", {}))
        translated = set(translations[translation_key(condition)].get("fields", {}))
        assert described == translated, condition


def test_condition_translation_names_do_not_include_ghost() -> None:
    """Test condition translation names do not include Spook's ghost marker."""
    assert all("👻" not in condition["name"] for condition in _translations().values())
