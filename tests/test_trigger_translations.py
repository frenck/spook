"""Tests for Spook trigger descriptors and translations.

The same contract the conditions have: a trigger without a descriptor is
dropped from the automation editor entirely, and a field without a
translation renders as its raw key. Neither fails anywhere else.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from custom_components.spook.trigger import async_get_triggers

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

SPOOK_ROOT = Path(__file__).parents[1] / "custom_components" / "spook"


def _descriptors() -> dict:
    """Return the trigger descriptors."""
    return yaml.safe_load((SPOOK_ROOT / "triggers.yaml").read_text())


def _translations() -> dict:
    """Return the English trigger translations."""
    return json.loads((SPOOK_ROOT / "translations" / "en.json").read_text())["triggers"]


async def test_every_trigger_has_a_descriptor(hass: HomeAssistant) -> None:
    """Test every discovered trigger is described in triggers.yaml."""
    assert set(await async_get_triggers(hass)) == set(_descriptors())


def test_every_trigger_has_translations() -> None:
    """Test every described trigger has a matching translation."""
    assert set(_descriptors()) == set(_translations())


def test_every_trigger_field_has_translations() -> None:
    """Test every described trigger field has a matching translation."""
    translations = _translations()

    for trigger, descriptor in _descriptors().items():
        described = set((descriptor or {}).get("fields", {}))
        translated = set(translations[trigger].get("fields", {}))
        assert described == translated, trigger


def test_trigger_translation_names_do_not_include_ghost() -> None:
    """Test trigger names carry no ghost of their own.

    Spook's actions get one appended while they are injected into another
    integration's domain. These live under `spook.` and are named plainly.
    """
    assert all("👻" not in trigger["name"] for trigger in _translations().values())
